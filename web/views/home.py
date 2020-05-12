import datetime
import json

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django_redis import get_redis_connection

from utils.alipay import AliPay
from utils.encrypt import uid
from web import models


def index(request):
    return render(request, 'web/index.html')


def price(request):
    """价格套餐"""
    policy_list = models.PricePolicy.objects.filter(category=2)
    return render(request, 'web/price.html', locals())


def payment(request, policy_id):
    """支付页面"""
    # 1、价格策略
    policy_object = models.PricePolicy.objects.filter(id=policy_id, category=2).first()
    if not policy_object:
        return redirect('price')

    # 2、购买数量
    number = request.GET.get('number', '')
    if not number or not number.isdecimal():
        return redirect('price')
    number = int(number)
    if number < 1:
        return redirect('price')

    # 3、计算价格
    origin_price = number * policy_object.price

    # 4、之前已经购买过套餐 的情况
    balance = 0  # 计算可以抵扣多少钱
    _object = None
    if request.lxyker.price_policy.category == 2:
        # 找到之前的订单
        _object = models.Transaction.objects.filter(user=request.lxyker.user, status=2).order_by('-id').first()
        total_timedelta = _object.end_datetime - _object.start_datetime
        balance_timedelta = _object.end_datetime - datetime.datetime.now()
        balance = _object.price / total_timedelta * balance_timedelta.days
    if balance >= origin_price:
        return redirect('price')

    context = {
        'policy_id': policy_object.id,
        'number': number,
        'origin_price': origin_price,
        'balance': round(balance, 2),
        'total_price': origin_price - round(balance, 2),
    }

    # 将支付信息存储到redis中，便于后面的pay函数获取支付信息，再传到支付宝
    conn = get_redis_connection()
    key = 'payment_{}'.format(request.lxyker.user.mobile_phone)
    conn.set(key, json.dumps(context), nx=60 * 30)

    context['policy_object'] = policy_object
    context['transaction'] = _object

    return render(request, 'web/payment.html', context)


def pay(request):
    """生成订单+支付宝支付"""
    # 直接从redis中取出要支付的订单信息
    conn = get_redis_connection()
    key = 'payment_{}'.format(request.lxyker.user.mobile_phone)
    context = conn.get(key)
    if not context:
        return redirect('price')
    context = json.loads(context.decode('utf-8'))

    # 1、数据库中生成交易记录（待支付）
    order_id = uid(request.lxyker.user.mobile_phone)
    total_price = context['total_price']
    models.Transaction.objects.create(
        status=1,
        order=order_id,
        user=request.lxyker.user,
        price_policy_id=context['policy_id'],
        count=context['number'],
        price=total_price,
    )

    # 2、跳转到支付宝链接进行支付：

    ali_pay = AliPay(
        appid=settings.ALI_APPID,
        app_notify_url=settings.ALI_NOTIFY_URL,
        return_url=settings.ALI_RETURN_URL,
        app_private_key_path=settings.ALI_PRI_KEY_PATH,
        alipay_public_key_path=settings.ALI_PUB_KEY_PATH,
    )
    query_params = ali_pay.direct_pay(
        subject="lxyker payment",  # 商品简单描述
        out_trade_no=order_id,  # 商户订单号
        total_amount=total_price
    )
    pay_url = "{}?{}".format(settings.ALI_GATEWAY, query_params)

    return redirect(pay_url)


def pay_notify(request):
    """支付成功之后触发的URL"""
    ali_pay = AliPay(
        appid=settings.ALI_APPID,
        app_notify_url=settings.ALI_NOTIFY_URL,
        return_url=settings.ALI_RETURN_URL,
        app_private_key_path=settings.ALI_PRI_KEY_PATH,
        alipay_public_key_path=settings.ALI_PUB_KEY_PATH,
    )

    if request.method == 'GET':
        # 只做跳转，判断是否支付成功了，不做订单的状态更新。
        # 支付吧会讲订单号返回：获取订单ID，然后根据订单ID做状态更新 + 认证。
        # 支付宝公钥对支付给我返回的数据request.GET 进行检查，通过则表示这是支付宝返还的接口。
        params = request.GET.dict()
        sign = params.pop('sign', None)
        status = ali_pay.verify(params, sign)
        if status:
            # """
            current_datetime = datetime.datetime.now()
            out_trade_no = params['out_trade_no']
            _object = models.Transaction.objects.filter(order=out_trade_no).first()

            _object.status = 2
            _object.start_datetime = current_datetime
            _object.end_datetime = current_datetime + datetime.timedelta(days=365 * _object.count)
            _object.save()
            # """
            return HttpResponse('支付完成')
        return HttpResponse('支付失败')
    elif request.method == 'POST':
        from urllib.parse import parse_qs
        body_str = request.body.decode('utf-8')
        post_data = parse_qs(body_str)
        post_dict = {}
        for k, v in post_data.items():
            post_dict[k] = v[0]

        sign = post_dict.pop('sign', None)
        status = ali_pay.verify(post_dict, sign)
        if status:
            current_datetime = datetime.datetime.now()
            out_trade_no = post_dict['out_trade_no']
            _object = models.Transaction.objects.filter(order=out_trade_no).first()

            _object.status = 2
            _object.start_datetime = current_datetime
            _object.end_datetime = current_datetime + datetime.timedelta(days=365 * _object.count)
            _object.save()
            return HttpResponse('success')

        return HttpResponse('error')
