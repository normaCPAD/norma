from norma.models.base import CPADModel
from norma.models.discrete import DiscreteCPAD
from norma.models.linear import LinearCPAD
from norma.models.order import OrderCPAD
from norma.models.ensemble import EnsembleCPAD
from norma.models.routed import RoutedCPAD

__all__ = ["CPADModel", "DiscreteCPAD", "LinearCPAD", "OrderCPAD",
           "EnsembleCPAD", "RoutedCPAD"]


def GatedCPAD(*args, **kwargs):
    """Lazy accessor for the torch-based variant (keeps torch an optional dependency)."""
    from norma.models.gated import GatedCPAD as _GatedCPAD
    return _GatedCPAD(*args, **kwargs)
