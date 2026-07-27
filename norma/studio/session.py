"""NormaSession -- the application's data model and orchestration layer.

Holds the loaded table, the fitted CPAD model, the (editable) constraint set, the
per-cell anomaly scores and the derived relational schema. Everything the UI shows is
recomputed from the *enabled* constraints, so toggling a rule or adding an expert one
updates the FD graph, the schema and the SQL live. Communicates with the widgets through
Qt signals.
"""
from __future__ import annotations
import os
from dataclasses import dataclass, field
import numpy as np
import pandas as pd
from PySide6.QtCore import QObject, Signal

from norma.core.table import Table

# Working-set cap: discovering FDs/DCs needs a representative sample, not every row, so we
# bound how many rows the app loads. This keeps a multi-GB file from exhausting memory (a
# "Python" crash) or freezing the UI. Override with NORMA_MAX_ROWS=0 to load everything.
_env = os.environ.get("NORMA_MAX_ROWS", "200000")
MAX_ROWS = int(_env) if _env.isdigit() and int(_env) > 0 else None


def _read_cap():
    """Rows to request from a reader: one past the cap, so we can detect truncation."""
    return (MAX_ROWS + 1) if MAX_ROWS is not None else None
from norma.core.constraint import FunctionalDependency, DenialConstraint, LinearConstraint
from norma.models import RoutedCPAD
from norma.modeling.closure import as_pairs, candidate_keys, minimal_cover
from norma.modeling.normalize import synthesize_3nf, decompose_bcnf
from norma.studio.i18n import t
from norma.modeling.report import _kind, _normal_form
from norma.repair import repair_table, RepairConfig
from norma.quality import quality_metrics, build_html_report


@dataclass
class RuleItem:
    """A constraint shown in the UI: the underlying object, its kind, whether it is
    enabled, and whether it came from the miner or from an expert."""
    obj: object
    kind: str
    enabled: bool = True
    source: str = "discovered"          # or "expert"

    @property
    def text(self) -> str:
        return str(self.obj)

    @property
    def confidence(self) -> float:
        return float(getattr(self.obj, "confidence", 1.0))


@dataclass
class SchemaModel:
    attributes: list = field(default_factory=list)
    keys: list = field(default_factory=list)
    normal_form: str = "n/a"
    relations_3nf: list = field(default_factory=list)
    relations_bcnf: list = field(default_factory=list)


class NormaSession(QObject):
    tableLoaded = Signal(object)        # pandas.DataFrame
    analyzed = Signal()
    rulesChanged = Signal()
    schemaChanged = Signal()
    scoresChanged = Signal()
    repairReady = Signal()
    repaired = Signal()
    status = Signal(str)

    def __init__(self):
        super().__init__()
        self.table: Table | None = None
        self.model: RoutedCPAD | None = None
        self.rules: list[RuleItem] = []
        self.scores: np.ndarray | None = None
        self.schema = SchemaModel()
        self.repair_result = None
        self._backup = None

    # -- loading -------------------------------------------------------------
    def load_csv(self, path: str):
        df = pd.read_csv(path, dtype=str, nrows=_read_cap()).fillna("")
        self.load_dataframe(df, name=path.rsplit("/", 1)[-1].rsplit(".", 1)[0])

    def load_path(self, path: str):
        """Load any supported format (CSV / Parquet / Excel / JSON) via Table.from_any.

        Reads at most MAX_ROWS+1 rows so a huge file never loads in full (bounded memory)."""
        tbl = Table.from_any(path, nrows=_read_cap())
        self.load_dataframe(tbl.df, name=tbl.name)

    def load_dataframe(self, df: pd.DataFrame, name: str = "table"):
        truncated = MAX_ROWS is not None and len(df) > MAX_ROWS
        if truncated:
            df = df.head(MAX_ROWS)
        self.table = Table(df.astype(str).fillna(""), name=name)
        self.model = None
        self.rules = []
        self.scores = None
        self.schema = SchemaModel()
        if truncated:
            self.status.emit(t("status_truncated").format(n=MAX_ROWS))
        else:
            self.status.emit(t("status_loaded").format(name=name, n=self.table.n,
                                                       c=len(self.table.columns)))
        self.tableLoaded.emit(df)
        self.rulesChanged.emit()
        self.schemaChanged.emit()
        self.scoresChanged.emit()

    def refresh_all(self):
        """Re-emit every signal so freshly built widgets repopulate (used after a UI
        rebuild, e.g. on a language change)."""
        if self.table is not None:
            self.tableLoaded.emit(self.table.df)
        self.rulesChanged.emit(); self.schemaChanged.emit(); self.scoresChanged.emit()

    # -- analysis ------------------------------------------------------------
    def compute_analysis(self):
        """Pure, thread-safe computation (no Qt, no state mutation): fit + score.
        Returns (model, scores) to be handed to `apply_analysis` on the main thread."""
        model = RoutedCPAD().fit(self.table)
        try:
            scores = model.score(self.table)
        except Exception:
            scores = np.zeros((self.table.n, len(self.table.columns)))
        return model, scores

    def apply_analysis(self, model, scores):
        """Install the computed results and notify the UI (main thread)."""
        self.model = model
        discovered = [RuleItem(o, _kind(o)) for o in model.rules()]
        experts = [r for r in self.rules if r.source == "expert"]
        self.rules = discovered + experts
        self.scores = scores
        self.rebuild_schema()
        self.status.emit(t("status_analyzed").format(k=len(discovered)))
        self.analyzed.emit(); self.rulesChanged.emit(); self.scoresChanged.emit()

    def analyze(self):
        if self.table is None:
            return
        self.status.emit(t("status_analyzing"))
        model, scores = self.compute_analysis()
        self.apply_analysis(model, scores)

    # -- editing -------------------------------------------------------------
    def enabled_fds(self) -> list[FunctionalDependency]:
        return [r.obj for r in self.rules
                if r.enabled and isinstance(r.obj, FunctionalDependency)]

    def set_enabled(self, index: int, enabled: bool):
        if 0 <= index < len(self.rules):
            self.rules[index].enabled = enabled
            self.rebuild_schema()
            self.rulesChanged.emit()

    def add_expert_fd(self, lhs: list[str], rhs: str):
        fd = FunctionalDependency(tuple(lhs), rhs, confidence=1.0, support=1.0)
        self.rules.append(RuleItem(fd, "FD", enabled=True, source="expert"))
        self.rebuild_schema()
        self.status.emit(t("status_expert_added").format(fd=fd))
        self.rulesChanged.emit()

    def remove_rule(self, index: int):
        if 0 <= index < len(self.rules):
            del self.rules[index]
            self.rebuild_schema()
            self.rulesChanged.emit()

    def set_external_relations(self, rels):
        """Display a schema parsed from hand-edited SQL (SQL -> visual). `rels` is a list
        of (name, attributes, key)."""
        from norma.modeling.normalize import Relation
        relations = [Relation(name, frozenset(attrs), frozenset(key), [])
                     for name, attrs, key in rels]
        self.schema.relations_bcnf = relations
        self.schema.relations_3nf = relations
        self.schemaChanged.emit()

    # -- schema synthesis ----------------------------------------------------
    def rebuild_schema(self):
        fds = self.enabled_fds()
        if not fds:
            self.schema = SchemaModel(attributes=(self.table.modeling_columns() if self.table else []))
            self.schemaChanged.emit()
            return
        attrs = sorted({a for fd in fds for a in (set(fd.lhs) | {fd.rhs})})
        pairs = as_pairs(fds)
        cover = minimal_cover(pairs)
        keys = candidate_keys(attrs, cover)
        self.schema = SchemaModel(
            attributes=attrs,
            keys=keys,
            normal_form=_normal_form(attrs, cover, keys),
            relations_3nf=synthesize_3nf(attrs, pairs),
            relations_bcnf=decompose_bcnf(attrs, pairs),
        )
        self.schemaChanged.emit()

    # -- repair & quality ----------------------------------------------------
    def enabled_objects(self):
        return [r.obj for r in self.rules if r.enabled]

    def compute_repair(self, config: RepairConfig | None = None):
        if self.table is None:
            return
        self.repair_result = repair_table(self.table.df, self.enabled_objects(),
                                          config or RepairConfig(), self.table.kinds)
        self.status.emit(t("status_repair_preview").format(n=self.repair_result.n_edits))
        self.repairReady.emit()

    def apply_repair(self):
        if self.repair_result is None or self.repair_result.n_edits == 0:
            return
        self._backup = self.table.df.copy()
        self.table = Table(self.repair_result.repaired, name=self.table.name)
        if self.model is not None:
            try:
                self.scores = self.model.score(self.table)
            except Exception:
                pass
        self.status.emit(t("status_repair_applied").format(n=self.repair_result.n_edits))
        self.tableLoaded.emit(self.table.df); self.scoresChanged.emit(); self.repaired.emit()

    def undo_repair(self):
        if self._backup is None:
            return
        self.table = Table(self._backup, name=self.table.name); self._backup = None
        if self.model is not None:
            try:
                self.scores = self.model.score(self.table)
            except Exception:
                pass
        self.status.emit(t("status_repair_undone"))
        self.tableLoaded.emit(self.table.df); self.scoresChanged.emit(); self.repaired.emit()

    def quality_html(self) -> str:
        from norma.studio import i18n
        if self.table is None:
            return f"<p style='font-family:sans-serif;color:#667'>{i18n.t('ready')}</p>"
        m = quality_metrics(self.table, self.schema, self.scores)
        anomalies = self.model.explain(self.table, k=15) if self.model is not None else []
        return build_html_report(self.table, self.enabled_objects(), self.schema, m, anomalies,
                                 self.repair_result, lang=i18n.language())

    # -- ecosystem export & contract -----------------------------------------
    def build_report(self, top: int = 15):
        """A DataModelReport built from the *enabled* constraints (so it reflects the user's
        toggles and expert rules), feeding norma.export and norma.contract."""
        from norma.modeling.report import DataModelReport, _annotate_reason, _governed_columns
        rules = self.enabled_objects()
        anomalies = self.model.explain(self.table, k=top) if self.model is not None else []
        _annotate_reason(anomalies, _governed_columns(rules))
        return DataModelReport(self.table.name, self.schema.attributes, rules,
                               self.schema.keys, self.schema.normal_form,
                               self.schema.relations_3nf, self.schema.relations_bcnf, anomalies)
