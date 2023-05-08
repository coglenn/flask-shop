import time, re
from datetime import datetime

from flask import (
    Blueprint,
    abort,
    redirect,
    render_template,
    request,
    url_for,
)

from flask_babel import lazy_gettext
from flask_login import current_user, login_required
from pluggy import HookimplMarker

from flaskshop.constant import OrderStatusKinds, PaymentStatusKinds, ShipStatusKinds
from flaskshop.extensions import csrf_protect
# from .payment import zhifubao
import stripe
from .models import Order, OrderPayment, OrderLine


stripe.api_key = 'sk_test_51N4QgvJs9hh3tFE1WZuvEtRkdsrvJzZnh4hlJMDE08snk478wGBuMpHvLFZlKtxK53XvAlP23YJqHl5F2wnjeYed0097p4sGbR'


impl = HookimplMarker("flaskshop")


@login_required
def index():
    return redirect(url_for("account.index"))


@login_required
def show(token):
    order = Order.query.filter_by(token=token).first()
    if not order.is_self_order:
        abort(403, lazy_gettext("This is not your order!"))
    return render_template("orders/details.html", order=order)


def create_payment(token, payment_method):
    order = Order.query.filter_by(token=token).first()
    if order.status != OrderStatusKinds.unfulfilled.value:
        abort(403, lazy_gettext("This Order Can Not Be Completed"))
    payment_no = str(int(time.time())) + str(current_user.id)
    customer_ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)
    payment = OrderPayment.query.filter_by(order_id=order.id).first()
    if payment:
        payment.update(
            payment_method=payment_method,
            payment_no=payment_no,
            customer_ip_address=customer_ip_address,
        )
    else:
        payment = OrderPayment.create(
            order_id=order.id,
            payment_method=payment_method,
            payment_no=payment_no,
            status=PaymentStatusKinds.waiting.value,
            total=order.total,
            customer_ip_address=customer_ip_address,
        )
    if payment_method == "alipay":
        redirect_url = zhifubao.send_order(order.token, payment_no, order.total)
        payment.redirect_url = redirect_url
    return payment


# @login_required
# def ali_pay(token):
#     payment = create_payment(token, "alipay")
#     return redirect(payment.redirect_url)
#
#
# @csrf_protect.exempt
# def ali_notify():
#     data = request.form.to_dict()
#     success = zhifubao.verify_order(data)
#     if success:
#         order_payment = OrderPayment.query.filter_by(
#             payment_no=data["out_trade_no"]
#         ).first()
#         order_payment.pay_success(paid_at=data["gmt_payment"])
#         return "SUCCESS"
#     return "ERROR HAPPEND"



# def create_checkout_session(token):
#     try:
#         checkout_session = stripe.checkout.Session.create(
#             line_items=[
#                 {
#                     # Provide the exact Price ID (for example, pr_1234) of the product you want to sell
#                     'price': 'price_1N4VYWJs9hh3tFE1lbS7ppli',
#                     'quantity': 1,
#                 },
#             ],
#             mode='payment',
#             success_url= 'http://127.0.0.1' + '/orders/payment_success.html',
#             cancel_url= 'http://127.0.0.1' + '/orders/details.html',
#             automatic_tax={'enabled': True},
#         )
#     except Exception as e:
#         return str(e)
#
#     return redirect(checkout_session.url, code=303)


@login_required
def test_pay_flow(token):
    payment = create_payment(token, "strip_pay")
    order = Order.query.filter_by(token=token).first()
    payment = OrderPayment.query.filter_by(order_id=order.id).first()
    stripe_pmt = OrderLine.query.filter_by(order_id=order.id).first()
    line_id_is = re.sub('\D', '', str(stripe_pmt))
    strip_price = OrderLine.query.get(line_id_is)
    try:
        checkout_session = stripe.checkout.Session.create(
        line_items=[
            {
                # Provide the exact Price ID (for example, pr_1234) of the product you want to sell
                # 'price': 'price_1N4VYWJs9hh3tFE1lbS7ppli',
                'price': strip_price.stripe_price_id,
                'quantity': strip_price.quantity,
            },
        ],
        mode='payment',
        success_url= 'http://127.0.0.1:5000' + '/orders/payment_success',
        cancel_url= 'http://127.0.0.1:5000' + '/orders/' + str(token),
        automatic_tax={'enabled': True},
        )
        # if checkout_session.payment_status != 'unpaid':
        #     print(checkout_session)
        #     payment.pay_success(paid_at=datetime.now())
    except Exception as e:
        return str(e)
    # if success_url is not None:
    #     payment.pay_success(paid_at=datetime.now())
    # payment.pay_success(paid_at=datetime.now())
    # return redirect(url_for("order.payment_success"))
    return redirect(checkout_session.url, code=303)


@login_required
def payment_success():
    # payment_no = request.args.get("success_url")
    # if payment_no:
    #     res = zhifubao.query_order(payment_no)
    #     if res["code"] == "303":
    #         order_payment = OrderPayment.query.filter_by(
    #             payment_no=res["out_trade_no"]
    #         ).first()
    #         order_payment.pay_success(paid_at=res["send_pay_date"])
    #     else:
    #         print(res["msg"])

    return render_template("orders/checkout_success.html")


@login_required
def cancel_order(token):
    order = Order.query.filter_by(token=token).first()
    if not order.is_self_order:
        abort(403, "This is not your order!")
    order.cancel()
    return render_template("orders/details.html", order=order)


@login_required
def receive(token):
    order = Order.query.filter_by(token=token).first()
    order.update(
        status=OrderStatusKinds.completed.value,
        ship_status=ShipStatusKinds.received.value,
    )
    return render_template("orders/details.html", order=order)


@impl
def flaskshop_load_blueprints(app):
    bp = Blueprint("order", __name__)
    bp.add_url_rule("/", view_func=index)
    bp.add_url_rule("/<string:token>", view_func=show)
    # bp.add_url_rule("/pay/<string:token>/alipay", view_func=ali_pay)
    # bp.add_url_rule("/alipay/notify", view_func=ali_notify, methods=["POST", "HEAD"])
    bp.add_url_rule("/pay/<string:token>/testpay", view_func=test_pay_flow)
    bp.add_url_rule("/payment_success", view_func=payment_success)
    bp.add_url_rule("/cancel/<string:token>", view_func=cancel_order)
    bp.add_url_rule("/receive/<string:token>", view_func=receive)
    app.register_blueprint(bp, url_prefix="/orders")
