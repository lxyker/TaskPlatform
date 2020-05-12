import datetime

from django.conf import settings
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin

from web import models


class Lxyker:
    def __init__(self):
        self.user = None
        self.price_policy = None
        self.project = None


class AuthMiddleware(MiddlewareMixin):

    def process_request(self, request):
        request.lxyker = Lxyker()
        user_id = request.session.get('user_id')
        request.lxyker.user = models.UserInfo.objects.filter(id=user_id).first() if user_id else None

        # 白名单
        """
        1、获取当前用户访问的URL
        2、判断这个URL是否在白名单中
            - 在——>继续访问
            - 不在——>判断是否登录
        """
        if request.path_info in settings.WHITE_REGEX_URL_LIST: return

        if not request.lxyker.user: return redirect('login')

        # 找到用户的最新购买记录（正在使用的）
        obj = models.Transaction.objects.filter(user=request.lxyker.user, status=2).order_by('-id').first()
        # 这个交易obj是否过期？
        if obj.end_datetime and obj.end_datetime < datetime.datetime.now():
            # 交易购买了但过期了
            obj = models.Transaction.objects.filter(
                user=request.lxyker.user, status=2, price_policy__category=1
            ).order_by('-id').first()
        # 将用户的购买额度存入自造的对象lxyker     ↓↓
        request.lxyker.price_policy = obj.price_policy

    def process_view(self, request, view, args, kwargs):
        # 判断URL是否以manage开头：
        #     - 是：已经进入了项目——>判断项目id是否为自己创建或参与
        if not request.path_info.startswith('/manage/'): return

        project_id = kwargs.get('project_id')

        created_project = models.Project.objects.filter(creator=request.lxyker.user, id=project_id).first()
        if created_project:  # 是自己创建的项目
            request.lxyker.project = created_project
            return
        joined_project = models.ProjectUser.objects.filter(user=request.lxyker.user, id=project_id).first()
        if joined_project:  # 是自己参与的项目
            request.lxyker.project = joined_project
            return

        # 既不是自己创建的项目，也不是自己参与的项目
        return redirect('project_list')
