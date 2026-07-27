"""Assemble a data model from a fitted CPAD model: discovered constraints, candidate
keys, the current normal form, a proposed 3NF/BCNF decomposition, and the worst
constraint-violating cells. `DataModelReport` renders to text or to a JSON-able dict.
"""
from __future__ import annotations
from dataclasses import dataclass, field

from norma.core.table import Table
from norma.core.constraint import FunctionalDependency
from norma.models.base import CPADModel
from norma.modeling.closure import as_pairs, attribute_closure, candidate_keys, minimal_cover
from norma.modeling.normalize import synthesize_3nf, decompose_bcnf, Relation


def _kind(c) -> str:
    if hasattr(c, "rhs"):                                 # FunctionalDependency
        return "composite-DC" if c.is_composite else "FD"
    if hasattr(c, "coefficients"):                        # LinearConstraint
        return "linear-DC"
    return "order-DC"                                     # DenialConstraint (order predicates)


def _normal_form(all_attrs, cover, keys) -> str:
    prime = set().union(*keys) if keys else set(all_attrs)
    bcnf, three = True, True
    for lhs, rhs in cover:
        if rhs in lhs:
            continue
        superkey = attribute_closure(lhs, cover) >= set(all_attrs)
        if not superkey:
            bcnf = False
            if rhs not in prime:
                three = False
    if bcnf:
        return "BCNF"
    return "3NF" if three else "lower than 3NF"


@dataclass
class DataModelReport:
    table_name: str
    attributes: list
    rules: list                                          # list[FunctionalDependency]
    keys: list                                           # list[frozenset]
    normal_form: str
    relations_3nf: list                                  # list[Relation]
    relations_bcnf: list
    anomalies: list = field(default_factory=list)

    def to_dict(self):
        return {
            "table": self.table_name,
            "attributes": self.attributes,
            "discovered_constraints": [
                {"rule": str(c), "denial_constraint": str(c.to_dc() if hasattr(c, "to_dc") else c),
                 "confidence": c.confidence, "kind": _kind(c)}
                for c in self.rules],
            "candidate_keys": [sorted(k) for k in self.keys],
            "current_normal_form": self.normal_form,
            "proposed_3nf": [r.to_dict() for r in self.relations_3nf],
            "proposed_bcnf": [r.to_dict() for r in self.relations_bcnf],
            "top_violations": self.anomalies,
        }

    def to_text(self) -> str:
        L = []
        L.append(f"# Data model for '{self.table_name}'  ({len(self.attributes)} attributes)")
        L.append(f"\n## Discovered constraints ({len(self.rules)})")
        for c in sorted(self.rules, key=lambda c: (-getattr(c, "arity", 0), -c.confidence)):
            label = {"FD": "FD", "composite-DC": "DC (composite)",
                     "order-DC": "DC (order)", "linear-DC": "DC (linear)"}[_kind(c)]
            L.append(f"  [{label:14}] {c}    (conf {c.confidence:.3f})")
        if not self.rules:
            L.append("  (none)")
        L.append("\n## Candidate keys")
        for k in self.keys:
            L.append(f"  {{{', '.join(sorted(k))}}}")
        L.append(f"\n## Current normal form: {self.normal_form}")
        L.append("\n## Proposed 3NF decomposition")
        for r in self.relations_3nf:
            L.append(f"  {r.name}({', '.join(sorted(r.attributes))})  key={{{', '.join(sorted(r.key))}}}")
        L.append("\n## Proposed BCNF decomposition")
        for r in self.relations_bcnf:
            L.append(f"  {r.name}({', '.join(sorted(r.attributes))})  key={{{', '.join(sorted(r.key))}}}")
        if self.anomalies:
            L.append("\n## Top constraint-violating cells")
            for a in self.anomalies:
                L.append(f"  row {a['row']:>6}  {a['column']} = {a['value']!r}   (score {a['score']:.3f})")
        return "\n".join(L)

    def _repr_html_(self) -> str:
        import html
        rows = "".join(
            f"<tr><td><code>{_kind(c)}</code></td><td><code>{html.escape(str(c))}</code></td>"
            f"<td style='text-align:right'>{c.confidence:.3f}</td></tr>"
            for c in sorted(self.rules, key=lambda c: (-getattr(c, "arity", 0), -c.confidence)))
        keys = ", ".join("{" + ", ".join(sorted(k)) + "}" for k in self.keys) or "&mdash;"
        anoms = ""
        for a in self.anomalies:
            viol = a.get("reason", "").startswith("violates")
            chip = ("#b00020" if viol else "#8a6d00")
            bg = ("#fde7ea" if viol else "#fff6da")
            anoms += (f"<tr><td>{a['row']}</td><td><code>{html.escape(str(a['column']))}</code></td>"
                      f"<td><code>{html.escape(str(a['value']))}</code></td>"
                      f"<td style='text-align:right'>{a['score']:.3f}</td>"
                      f"<td style='color:{chip};background:{bg};border-radius:4px;padding:0 6px'>"
                      f"{html.escape(a.get('reason', ''))}</td></tr>")
        anoms_block = (f"<h4>Top violations &mdash; <span style='color:#b00020'>constraint "
                       f"violation</span> vs <span style='color:#8a6d00'>rare-but-valid</span></h4>"
                       f"<table><tr><th>row</th><th>column</th><th>value</th><th>score</th>"
                       f"<th>reason</th></tr>{anoms}</table>") if self.anomalies else ""
        return (f"<div style='font-family:system-ui'>"
                f"<h3>NORMA data model &mdash; <code>{html.escape(self.table_name)}</code></h3>"
                f"<p><b>Normal form:</b> {html.escape(self.normal_form)} &nbsp;|&nbsp; "
                f"<b>{len(self.rules)}</b> constraints &nbsp;|&nbsp; "
                f"<b>{len(self.attributes)}</b> attributes</p>"
                f"<p><b>Candidate keys:</b> {keys}</p>"
                f"<h4>Discovered constraints</h4>"
                f"<table><tr><th>kind</th><th>rule</th><th>conf</th></tr>{rows}</table>"
                f"{anoms_block}</div>")


def _governed_columns(rules) -> set:
    """Columns that some discovered constraint governs (FD lhs/rhs, linear/order attributes)."""
    g: set = set()
    for c in rules:
        if hasattr(c, "rhs"):
            g |= set(c.lhs) | {c.rhs}
        elif hasattr(c, "attributes"):
            g |= set(c.attributes)
    return g


def _annotate_reason(anomalies, governed):
    """Surface NORMA's thesis per cell: a relational violation vs a merely rare value.

    A flagged cell in a *governed* column breaks a constraint (a true data-quality error);
    a flagged cell elsewhere is only statistically rare (the rare-but-valid boundary)."""
    for a in anomalies:
        a["reason"] = ("violates a constraint" if a["column"] in governed
                       else "rare value (no governing constraint)")
    return anomalies


def build_model(table: Table, model: CPADModel, top_anomalies: int = 10) -> DataModelReport:
    rules = model.rules()                                 # mixed FDs and denial constraints
    fds: list[FunctionalDependency] = [r for r in rules if isinstance(r, FunctionalDependency)]
    attrs = sorted({a for fd in fds for a in (set(fd.lhs) | {fd.rhs})}) or table.modeling_columns()
    pairs = as_pairs(fds)
    cover = minimal_cover(pairs) if pairs else []
    keys = candidate_keys(attrs, cover) if cover else [frozenset(attrs)]
    nf = _normal_form(attrs, cover, keys) if cover else "n/a (no constraints found)"
    r3 = synthesize_3nf(attrs, pairs) if pairs else []
    rb = decompose_bcnf(attrs, pairs) if pairs else []
    anomalies = model.explain(table, k=top_anomalies) if top_anomalies else []
    _annotate_reason(anomalies, _governed_columns(rules))
    return DataModelReport(table.name, attrs, rules, keys, nf, r3, rb, anomalies)


def profile(table: Table, model: CPADModel | None = None, top: int = 10) -> DataModelReport:
    """Fit a model (default: the complete routed CPAD) and return its data-model report.

    Built for notebooks: ``profile(table)`` renders inline through ``_repr_html_``."""
    if model is None:
        from norma.models import RoutedCPAD
        model = RoutedCPAD()
    if not getattr(model, "rules_", None):
        model.fit(table)
    return build_model(table, model, top_anomalies=top)
