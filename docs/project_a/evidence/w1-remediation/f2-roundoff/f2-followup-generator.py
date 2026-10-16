from decimal import Decimal, localcontext
import json
import numpy as np
from pathlib import Path


def legendre(n, x):
    previous, value = Decimal(1), x
    for k in range(2, n + 1):
        previous, value = value, ((2 * k - 1) * x * value - (k - 1) * previous) / k
    derivative = n * (x * value - previous) / (x * x - 1)
    return value, derivative


rows = []
records = []
with localcontext() as context:
    context.prec = 100
    for initial in np.polynomial.legendre.leggauss(32)[0][16:]:
        x = Decimal.from_float(float(initial))
        for iteration in range(30):
            value, derivative = legendre(32, x)
            updated = x - value / derivative
            if abs(updated - x) < Decimal('1e-95'):
                x = updated
                break
            x = updated
        value, derivative = legendre(32, x)
        weight = 2 / ((1 - x * x) * derivative * derivative)
        rows.append((float(x), float(weight)))
        records.append({'root_decimal':str(x),'weight_decimal':str(weight),
                        'root_float':float(x),'weight_float':float(weight),
                        'root_residual_decimal':str(value),
                        'weight_relative_rounding':str(abs(Decimal.from_float(float(weight))-weight)/weight)})
    eps = Decimal(2) ** -52
    quadrature = [((1 + sign * x) / 2, w / 2)
                  for x, w in rows for sign in (-1, 1)]
    moments = []
    for degree in range(64):
        value = sum(Decimal.from_float(w) * Decimal.from_float(x) ** degree
                    for x, w in quadrature)
        exact = Decimal(1) / (degree + 1)
        moments.append({'degree': degree, 'absolute_error': str(abs(value - exact))})
    max_weight_error = max(Decimal(r['weight_relative_rounding']) for r in records)
    assert max_weight_error < eps / 2
    max_moment_error = max(Decimal(r['absolute_error']) for r in moments)
    assert max_moment_error < eps
print('_GAUSS_POSITIVE = (')
for row in rows:
    print('    ' + repr(row) + ',')
print(')')
Path('work/remediation/a02/gauss32-constants.json').write_text(json.dumps({
    'decimal_precision':100,'records':records,'mapped_polynomial_moments':moments,
    'max_float_weight_relative_error':str(max_weight_error),
    'max_mapped_moment_absolute_error':str(max_moment_error)},indent=2)+'\n')
