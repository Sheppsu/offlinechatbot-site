import math


__all__ = (
    "batch",
)


def batch(a, n):
    d, m = divmod(len(a), n)
    for i in range(d+(0 if m == 0 else 1)):
        yield a[i*n:(i+1)*n]
