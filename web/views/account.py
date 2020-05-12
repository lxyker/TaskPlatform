import datetime
import io
import uuid

from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse

from utils.image_code import check_code
from web.forms.account import *


def register(request):
    if request.method == 'GET':
        form = RegisterModelForm()
        return render(request, 'web/register.html', locals())
    form = RegisterModelForm(data=request.POST)
    if form.is_valid():
        # 注册数据校验成功，需在数据库创建这个用户，然后跳转到登录页
        instance = form.save()

        # 创建好用户，自动生成一条免费的交易记录   ↓↓
        price_policy_obj = models.PricePolicy.objects.filter(category=1).first()
        models.Transaction.objects.create(
            status=2,
            order=str(uuid.uuid4()),  # 随机字符串作为订单号
            user=instance,
            price_policy=price_policy_obj,
            count=0,
            price=0,
            start_datetime=datetime.datetime.now(),
        )

        return JsonResponse({'status': True, 'go_url': reverse('login')})
    return JsonResponse({'status': False, 'error': form.errors})


def send_sms(request):
    form = SendSmsForm(request, data=request.GET)
    if form.is_valid():
        return JsonResponse({'status': True})
    return JsonResponse({'status': False, 'error': form.errors})


def login_sms(request):
    if request.method == 'GET':
        form = LoginSMSForm(request)
        return render(request, 'web/login_sms.html', locals())
    form = LoginSMSForm(request, data=request.POST)
    if form.is_valid():
        # 登录form校验成功
        user_obj = form.cleaned_data['mobile_phone']
        if user_obj:
            # 将用户信息存入session
            request.session['user_id'] = user_obj.id
            request.session.set_expiry(60 * 60 * 24 * 30)  # 一月免登录
            return JsonResponse({'status': True, 'go_url': reverse('index')})
    return JsonResponse({'status': False, 'error': form.errors})


def login(request):
    if request.method == 'GET':
        form = LoginForm(request)
        return render(request, 'web/login.html', locals())
    form = LoginForm(request, data=request.POST)
    if form.is_valid():
        # 登录form校验成功
        user = form.cleaned_data['user']
        pwd = form.cleaned_data['password']
        user_obj = models.UserInfo.objects.filter(Q(username=user) | Q(mobile_phone=user)).filter(password=pwd).first()
        if user_obj:
            # 将用户信息存入session
            request.session['user_id'] = user_obj.id
            request.session.set_expiry(60 * 60 * 24 * 30)  # 一月免登录
            # print('登陆成功哦了    访问')
            # return redirect('index')
            return JsonResponse({'status': True, 'go_url': reverse('index')})
        form.add_error('password', '用户名或密码错误！')
    return JsonResponse({'status': False, 'error': form.errors})


def image_code(request):
    """验证码图片"""
    image_object, code = check_code()
    request.session['img_code'] = code
    request.session.set_expiry(90)  # 主动修改session过期时间
    stream = io.BytesIO()
    image_object.save(stream, 'png')
    return HttpResponse(stream.getvalue())


def logout(request):
    request.session.flush()
    return redirect('index')
