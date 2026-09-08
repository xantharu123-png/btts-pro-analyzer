"""Synthetic numerical mechanics; these tests certify no sport effect."""

import json
from types import SimpleNamespace

import numpy as np
import pytest

import context_models.offset as module
from context_models.offset import ContextModelError, fit_offset, offset_delta, adjust_parameters
from context_models.contracts import validate_offset_fit


def test_learned_count_effect_and_zero_reference():
    x = np.array([[-1.], [0.], [1.]] * 40)
    target = np.array([1., 2., 4.] * 40)
    model = fit_offset(x, np.full(120, np.log(2.)), target, link="log_rate", alpha=.1)
    delta = offset_delta(model, np.array([[0.], [1.]]))
    assert delta[0] == 0.
    assert delta[1] > 0.
    adjusted = adjust_parameters(np.array([2., 2.]), delta, link="log_rate")
    assert adjusted[0] == 2.
    assert adjusted[1] > adjusted[0]


def standalone_fit(**changes):
    return {"link": "identity", "scale": [2.], "coef": [3.], "alpha": .1, "n_rows": 10, **changes}


def training(link="identity", **changes):
    values = {"x": np.array([[-1.], [0.], [1.]] * 10), "offset": np.zeros(30),
              "target": np.array([0., 0., 1.] * 10), "link": link, "alpha": .1}
    values.update(changes)
    return values


def test_binomial_fit_learns_counts_and_supports_default_binary_trials():
    args = training("logit", target=np.array([2., 5., 8.] * 10), trials=np.full(30, 10.))
    fitted = fit_offset(**args)
    assert fitted["coef"][0] > 0
    probabilities = adjust_parameters(np.full(3, .5), offset_delta(fitted, np.array([[-1.], [0.], [1.]])), link="logit")
    assert probabilities[0] < .5 == probabilities[1] < probabilities[2]
    assert probabilities[0] + probabilities[2] == pytest.approx(1)
    binary = fit_offset(**training("logit"))
    explicit = fit_offset(**training("logit", trials=np.ones(30)))
    assert binary == explicit


def test_identity_fit_learns_real_negative_targets_against_offset_without_centering():
    x = np.array([[1.], [2.], [3.], [4.]])
    offset = np.full(4, -10.)
    target = offset + 2 * x[:, 0]
    fitted = fit_offset(x, offset, target, link="identity", alpha=0.)
    assert fitted["scale"] == pytest.approx(np.std(x, axis=0, ddof=0))
    assert offset_delta(fitted, np.array([[0.], [2.]])) == pytest.approx([0., 4.])
    assert fitted["coef"][0] / fitted["scale"][0] == pytest.approx(2.)


@pytest.mark.parametrize("link", ["log_rate", "logit", "identity"])
@pytest.mark.parametrize("alpha", [0., .3])
def test_exact_objective_gradient_agrees_with_independent_finite_differences(link, alpha):
    z = np.array([[-1., .3], [0., -.5], [2., .2], [-.4, 1.1]])
    offset = np.array([.3, -.2, 1., .4])
    target = np.array([1., 0., 3., 1.]) if link != "identity" else np.array([-2., .3, 2.1, -.8])
    trials = np.array([3., 2., 4., 3.]) if link == "logit" else None
    beta = np.array([.1, -.2])
    def fun(coeff):
        return module._objective_and_gradient(coeff, z, offset, target, link=link, alpha=alpha, trials=trials)
    value, gradient = fun(beta)
    numerical = np.empty(2)
    for index in range(2):
        step = np.zeros(2)
        step[index] = 1e-6
        numerical[index] = (fun(beta + step)[0] - fun(beta - step)[0]) / (2e-6)
    eta = offset + z @ beta
    if link == "log_rate": expected_loss = np.mean(np.exp(eta) - target * eta)
    elif link == "logit": expected_loss = np.mean(trials * np.log1p(np.exp(eta)) - target * eta)
    else: expected_loss = .5 * np.mean((eta - target) ** 2)
    assert value == pytest.approx(expected_loss + .5 * alpha * np.dot(beta, beta), rel=1e-13)
    assert gradient == pytest.approx(numerical, rel=1e-7, abs=1e-8)


@pytest.mark.parametrize("link", ["log_rate", "logit", "identity"])
def test_zero_training_columns_have_exact_zero_coefficients_and_do_not_add_intercept(link):
    args = training(link, x=np.zeros((30, 3)))
    fitted = fit_offset(**args)
    assert fitted["scale"] == [1e-8] * 3
    assert fitted["coef"] == [0.] * 3
    assert np.array_equal(offset_delta(fitted, np.ones((2, 3))), np.zeros(2))


def test_individual_zero_column_stays_zero_and_regularization_is_the_specified_penalty():
    args = training("identity")
    args["x"] = np.column_stack([args["x"], np.zeros(30)])
    low = fit_offset(**args)
    high = fit_offset(**{**args, "alpha": 100.})
    assert low["coef"][1] == high["coef"][1] == 0
    assert abs(high["coef"][0]) < abs(low["coef"][0])


@pytest.mark.parametrize("link", ["identity", "logit"])
def test_side_reversal_preserves_fit_and_reverses_predictions(link):
    args = training(link)
    first = fit_offset(**args)
    reverse_target = -args["target"] if link == "identity" else 1 - args["target"]
    second = fit_offset(**{**args, "x": -args["x"], "offset": -args["offset"], "target": reverse_target})
    assert first["coef"] == pytest.approx(second["coef"], abs=1e-12)
    a = offset_delta(first, np.array([[.7]]))
    b = offset_delta(second, np.array([[-.7]]))
    assert a == pytest.approx(-b)
    if link == "logit":
        p = adjust_parameters(np.array([.6]), a, link=link)
        reverse = adjust_parameters(np.array([.4]), b, link=link)
        assert p + reverse == pytest.approx(np.ones(1), abs=1e-12)


def test_stored_scale_is_reused_without_live_retraining_or_input_mutation():
    args = training()
    saved = {name: value.copy() for name, value in args.items() if isinstance(value, np.ndarray)}
    fitted = fit_offset(**args)
    payload = json.loads(json.dumps(fitted))
    one = np.array([[2.]])
    result = offset_delta(payload, one)
    assert result[0] == pytest.approx(2 / fitted["scale"][0] * fitted["coef"][0])
    assert offset_delta(payload, np.array([[2.], [2000.]]))[0] == result[0]
    assert np.array_equal(one, np.array([[2.]]))
    assert all(np.array_equal(args[name], value) for name, value in saved.items())
    assert payload == fitted


@pytest.mark.parametrize("link,base", [("log_rate", [1e-300, 1., 1e300]), ("logit", [1e-300, .123456789, .9]), ("identity", [-0., -1e200, 1.23456789])])
def test_zero_delta_preserves_exact_baseline_bytes(link, base):
    initial = np.array(base)
    assert adjust_parameters(initial, np.zeros(3), link=link).tobytes() == initial.tobytes()


@pytest.mark.parametrize("base,delta", [(1e-300, 800.), (1e300, -800.)])
def test_rate_inverse_joint_log_space_keeps_representable_extreme_result(base, delta):
    result = adjust_parameters(np.array([base]), np.array([delta]), link="log_rate")
    assert np.isfinite(result[0]) and result[0] > 0
    assert result[0] == pytest.approx(np.exp(np.log(base) + delta), rel=1e-13)


@pytest.mark.parametrize("link,base,delta", [("log_rate", 1., 1e6), ("log_rate", 1., -1e6),
    ("log_rate", 0., 0.), ("log_rate", -1., 0.), ("logit", 0., 0.), ("logit", 1., 0.),
    ("logit", .5, 1000.), ("logit", .5, -1000.), ("identity", 1e308, 1e308)])
def test_impossible_adjustment_is_typed_error_not_clipped_or_zero_repair(link, base, delta):
    with pytest.raises(ContextModelError):
        adjust_parameters(np.array([base]), np.array([delta]), link=link)


BAD_ARRAYS = [np.array([True, False]), np.array(["1", "2"]), np.array([1., 2.], dtype=object),
              np.array([1+0j, 2+0j]), np.ma.array([1., 2.], mask=False), np.array([np.nan, 1.]),
              np.array([np.inf, 1.]), [1., 2.], np.array([2**53 + 1, 2], dtype=np.int64)]


@pytest.mark.parametrize("bad", BAD_ARRAYS)
@pytest.mark.parametrize("operation", ["fit_x", "fit_target", "fit_offset", "fit_trials", "predict", "adjust_base", "adjust_delta"])
def test_every_numeric_boundary_rejects_bad_actual_types_before_conversion(bad, operation):
    args = training(x=np.array([[-1.], [1.]]), offset=np.zeros(2), target=np.ones(2))
    with pytest.raises(ContextModelError):
        if operation == "fit_x": fit_offset(**{**args, "x": bad.reshape(2, 1) if hasattr(bad, "reshape") else bad})
        elif operation == "fit_target": fit_offset(**{**args, "target": bad})
        elif operation == "fit_offset": fit_offset(**{**args, "offset": bad})
        elif operation == "fit_trials": fit_offset(**{**args, "link": "logit", "trials": bad})
        elif operation == "predict": offset_delta(standalone_fit(), bad.reshape(2, 1) if hasattr(bad, "reshape") else bad)
        elif operation == "adjust_base": adjust_parameters(bad, np.zeros(2), link="identity")
        else: adjust_parameters(np.ones(2), bad, link="identity")


@pytest.mark.parametrize("changes", [{"x": np.ones((1, 1)), "offset": np.ones(1), "target": np.ones(1)},
    {"x": np.empty((30, 0))}, {"x": np.ones(30)}, {"offset": np.ones((30, 1))}, {"target": np.ones(1)},
    {"alpha": True}, {"alpha": -1}, {"alpha": float("nan")}, {"alpha": "0.1"}, {"link": "other"},
    {"link": []}, {"trials": np.ones(30)}])
def test_fit_rejects_shapes_unsupported_links_and_invalid_configuration(changes):
    with pytest.raises(ContextModelError):
        fit_offset(**training(**changes))


@pytest.mark.parametrize("link,changes", [("log_rate", {"target": np.full(30, -.5)}),
    ("log_rate", {"target": np.full(30, .5)}), ("logit", {"target": np.full(30, .5)}),
    ("logit", {"target": np.full(30, 2.)}), ("logit", {"trials": np.full(30, 1.5)}),
    ("logit", {"trials": np.zeros(30)}), ("logit", {"trials": np.ones((30, 1))}),
    ("logit", {"trials": np.ones(1)})])
def test_count_and_binomial_domains_do_not_round_or_broadcast(link, changes):
    with pytest.raises(ContextModelError):
        fit_offset(**training(link, **changes))


def test_count_valued_float_inputs_and_numeric_numpy_alpha_are_legal():
    assert fit_offset(**training("log_rate", alpha=np.float64(.1)))["n_rows"] == 30


@pytest.mark.parametrize("changes", [{"success": False}, {"success": "yes"}, {"x": np.array([np.nan])},
    {"jac": np.array([np.inf])}, {"fun": float("nan")}, {"fun": "1.0"}, {"x": np.ones(2)},
    {"jac": np.ones(2)}])
def test_optimizer_failures_and_nonfinite_claimed_success_never_publish_fit(monkeypatch, changes):
    result = SimpleNamespace(success=True, x=np.zeros(1), jac=np.zeros(1), fun=1.)
    result.__dict__.update(changes)
    monkeypatch.setattr(module.optimize, "minimize", lambda *a, **kw: result)
    with pytest.raises(ContextModelError):
        fit_offset(**training())


def test_optimizer_backend_exception_is_typed_not_silently_replaced(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("synthetic backend failure")
    monkeypatch.setattr(module.optimize, "minimize", fail)
    with pytest.raises(ContextModelError, match="optimization failed"):
        fit_offset(**training())


def test_optimizer_receives_exact_declared_method_zero_start_and_analytic_gradient(monkeypatch):
    original = module.optimize.minimize
    calls = []
    def checked(objective, initial, **kwargs):
        calls.append((initial.copy(), kwargs))
        value, gradient = objective(initial)
        assert np.isfinite(value)
        assert gradient.shape == initial.shape
        return original(objective, initial, **kwargs)
    monkeypatch.setattr(module.optimize, "minimize", checked)
    fit_offset(**training())
    assert len(calls) == 1
    assert np.array_equal(calls[0][0], np.zeros(1))
    assert calls[0][1] == {"jac": True, "method": "L-BFGS-B"}


def test_claimed_success_cannot_hide_invalid_returned_parameters(monkeypatch):
    result = SimpleNamespace(success=True, x=np.array([1e308]), jac=np.zeros(1), fun=0.)
    monkeypatch.setattr(module.optimize, "minimize", lambda *args, **kwargs: result)
    with pytest.raises(ContextModelError):
        fit_offset(**training())


def test_claimed_success_cannot_assign_effect_to_all_zero_training_column(monkeypatch):
    result = SimpleNamespace(success=True, x=np.ones(1), jac=np.zeros(1), fun=0.)
    monkeypatch.setattr(module.optimize, "minimize", lambda *args, **kwargs: result)
    with pytest.raises(ContextModelError, match="all-zero"):
        fit_offset(**training(x=np.zeros((30, 1))))


@pytest.mark.parametrize("changes", [{"x": np.full((30, 1), 1e308)}, {"offset": np.full(30, 1000.), "link": "log_rate"},
                                    {"offset": np.full(30, -1000.), "link": "log_rate"}, {"target": np.full(30, 1e308)}])
def test_nonfinite_scale_or_objective_cannot_be_published(changes):
    with pytest.raises(ContextModelError):
        fit_offset(**training(**changes))


@pytest.mark.parametrize("changes", [{"extra": 1}, {"link": "other"}, {"coef": [True]}, {"coef": [np.inf]},
    {"coef": []}, {"coef": [1., 2.]}, {"scale": [0.]}, {"scale": np.array([1.])},
    {"scale": [float("nan")]}, {"n_rows": 2.0}, {"n_rows": True}, {"alpha": -1.}])
def test_offset_prediction_uses_closed_shared_standalone_fit_validator(changes):
    with pytest.raises(ContextModelError):
        offset_delta(standalone_fit(**changes), np.ones((1, 1)))


@pytest.mark.parametrize("changes,expected", [({"scale": [10**20], "coef": [1]}, 1e-20),
                                            ({"scale": [1], "coef": [10**20]}, 1e20)])
def test_valid_large_json_integer_parameters_remain_numeric(changes, expected):
    model = validate_offset_fit(standalone_fit(**changes))
    result = offset_delta(model, np.ones((1, 1)))
    assert result.dtype == np.float64
    assert result[0] == pytest.approx(expected, rel=1e-14, abs=0.)


def test_prediction_shapes_and_overflow_are_errors_without_broadcasting():
    for x in (np.ones(1), np.ones((2, 2)), np.zeros((0, 1)), np.full((1, 1), 1e308)):
        with pytest.raises(ContextModelError):
            offset_delta(standalone_fit(scale=[1e-8], coef=[1e300]), x)
    for delta in (np.ones(1), np.ones((2, 1))):
        with pytest.raises(ContextModelError):
            adjust_parameters(np.ones(2), delta, link="identity")
