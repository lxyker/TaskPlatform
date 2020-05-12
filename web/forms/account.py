import random

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db.models import Q
from django_redis import get_redis_connection

from utils import encrypt
from utils.tencent.sms import send_sms_single
from web import models
from web.forms.bootstrap import BootStrapForm


class RegisterModelForm(BootStrapForm, forms.ModelForm):
    bootstrap_class_exclude = ['confirm_password']
    password = forms.CharField(
        label='密码',
        widget=forms.PasswordInput(),
        min_length=6,
        max_length=18,
        error_messages={'min_length': '密码不得少于6位', 'max_length': '密码不得超过18位'},
    )
    confirm_password = forms.CharField(
        label='重复密码',
        widget=forms.PasswordInput(attrs={'placeholder': '请重复密码', 'class': 'form-control'}),
    )
    code = forms.CharField(label='验证码', min_length=4, max_length=4)

    class Meta:
        model = models.UserInfo

        # fields = '__all__'    # 以默认顺序展示，需修改
        fields = ['username', 'email', 'password', 'confirm_password', 'mobile_phone', 'code']

    def clean_username(self):
        """校验用户名是否重复、是否可用"""
        username = self.cleaned_data['username']
        is_exists = models.UserInfo.objects.filter(username=username).exists()
        if is_exists:
            raise ValidationError('用户名已经存在！')
        return username

    def clean_password(self):
        """给密码加密"""
        pwd = self.cleaned_data['password']
        return encrypt.md5(pwd)

    def clean_confirm_password(self):
        """校验两次输入的密码是否一致"""
        pwd = self.cleaned_data['password']  # pwd是已加密的
        re_pwd = encrypt.md5(self.cleaned_data['confirm_password'])
        if pwd != re_pwd:
            raise ValidationError('两次密码不一致')
        return re_pwd

    def clean_mobile_phone(self):
        mobile_phone = self.cleaned_data['mobile_phone']
        is_exists = models.UserInfo.objects.filter(mobile_phone=mobile_phone).exists()
        if is_exists:
            raise ValidationError('该手机号已注册！')
        return mobile_phone

    def clean_code(self):
        code = self.cleaned_data['code']
        mobile = self.cleaned_data.get('mobile_phone')
        if not mobile:  # 手机号为空，用户没填直接返回
            return code
        conn = get_redis_connection()
        redis_code = conn.get(mobile)
        if not redis_code:
            raise ValidationError('验证码失效，请重新获取！')
        else:
            if redis_code == bytes(code, encoding='utf8'):
                return code
            else:
                raise ValidationError('验证码错误，请重新输入！')


class SendSmsForm(forms.Form):
    mobile_phone = forms.CharField(label='手机号', validators=[RegexValidator(r'^1[3,4,5,6,7,8]\d{9}$', '手机号格式错误'), ])

    def __init__(self, request, *args, **kwargs):
        super(SendSmsForm, self).__init__(*args, **kwargs)
        self.request = request

    def clean_mobile_phone(self):
        """钩子 校验手机号"""
        mobile_phone = self.cleaned_data['mobile_phone']

        # 校验tpl短信模板是否正确
        tpl = self.request.GET.get('tpl')
        template_id = settings.TENCENT_SMS_TEMPLATE.get(tpl)
        if not template_id:
            raise ValidationError('短信模板错误')

        # 校验数据库是否已经存在该手机号
        is_exists = models.UserInfo.objects.filter(mobile_phone=mobile_phone).exists()
        if tpl == 'register':
            if is_exists:
                raise ValidationError('该手机号已经注册！')
        elif tpl == 'login':
            if not is_exists:
                raise ValidationError('该手机号尚未注册！')

        # 发送短信，验证码写入redis，做完之后最后才返回
        code = str(random.randint(0, 9)) + str(random.randint(0, 9)) + str(random.randint(0, 9)) + str(
            random.randint(0, 9))
        # 发送短信
        sms = send_sms_single(mobile_phone, template_id, [code, ])
        if sms['result'] != 0:
            raise ValidationError('短信发送失败，{}'.format(sms['errmsg']))
        # 验证码写入redis
        conn = get_redis_connection()
        conn.set(mobile_phone, code, ex=60)  # 手机号作为键，验证码作为值

        return mobile_phone


class LoginForm(BootStrapForm, forms.Form):
    bootstrap_class_exclude = ['user']
    user = forms.CharField(
        label='账户',
        widget=forms.TextInput(
            attrs={'placeholder': '请输入用户名或手机号', 'class': 'form-control'},
        ),
    )
    password = forms.CharField(
        label='密码',
        widget=forms.PasswordInput(),
        min_length=6,
        max_length=18,
        error_messages={'min_length': '密码错误', 'max_length': '密码错误'},
    )
    code = forms.CharField(label='图片验证码')

    def __init__(self, request, *args, **kwargs):
        super(LoginForm, self).__init__(*args, **kwargs)
        self.request = request

    def clean_user(self):
        user = self.cleaned_data['user']
        usr_obj = models.UserInfo.objects.filter(Q(username=user) | Q(mobile_phone=user)).first()
        if usr_obj:
            return user
        raise ValidationError('该账户尚未注册！')

    def clean_password(self):
        pwd = self.cleaned_data['password']
        return encrypt.md5(pwd)

    def clean_code(self):
        """钩子函数校验 图片验证码"""
        ipt_code = self.cleaned_data['code']
        img_code = self.request.session.get('img_code')
        if not img_code:
            raise ValidationError('验证码已失效，请重新获取！')
        if ipt_code.lower() == img_code.lower():
            return img_code
        raise ValidationError('验证码错误，请重新输入！')


class LoginSMSForm(BootStrapForm, forms.Form):
    mobile_phone = forms.CharField(label='手机号', validators=[RegexValidator(r'^1[3,4,5,6,7,8]\d{9}$', '手机号格式错误'), ])
    code = forms.CharField(label='短信验证码')

    def __init__(self, request, *args, **kwargs):
        super(LoginSMSForm, self).__init__(*args, **kwargs)
        self.request = request

    def clean_mobile_phone(self):
        phone = self.cleaned_data['mobile_phone']
        usr_obj = models.UserInfo.objects.filter(mobile_phone=phone).first()
        if usr_obj:
            # 若填写手机正确，且数据库能查询到，则直接返回用户对象
            return usr_obj
        raise ValidationError('该账户尚未注册！')

    def clean_code(self):
        """钩子函数校验 短信验证码"""
        code = self.cleaned_data['code']
        phone = self.cleaned_data.get('mobile_phone').mobile_phone
        if not phone:
            # 如果手机号没能通过校验，那么这里是空
            return code
        # 这个手机号通过校验，则去redis中比较短信码是否一致
        conn = get_redis_connection()
        redis_code = conn.get(phone)
        if not redis_code:
            raise ValidationError('验证码失效，请重新获取！')
        else:
            if redis_code == bytes(code, encoding='utf8'):
                return code
            else:
                raise ValidationError('验证码错误，请重新输入！')