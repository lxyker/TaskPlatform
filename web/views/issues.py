import datetime
import json

from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.views.decorators.csrf import csrf_exempt

from utils.encrypt import uid
from utils.pagination import Pagination
from web import models
from web.forms.issues import IssuesModelForm, InviteModelForm, IssuesReplyModelForm


class CheckFilter:
    def __init__(self, name, data_list, request):
        self.name = name
        self.data_list = data_list
        self.request = request

    def __iter__(self):
        for item in self.data_list:
            key = str(item[0])
            text = item[1]
            ck = ''
            # 若 当前用户请求的URL中的status 和 当前循环的key 相等，ck就是'checked'
            value_list = self.request.GET.getlist(self.name)
            if key in value_list:
                ck = 'checked'
                value_list.remove(key)
            else:
                value_list.append(key)

            # 为自己生成URL，点击时就在后面增加相应的 &xx=1。在当前的URL基础上增加一项
            query_dict = self.request.GET.copy()
            query_dict._mutable = True  # 设置成True才能执行下面的setlist
            query_dict.setlist(self.name, value_list)

            # 如果在100页点击筛选条件，也应回到第一页
            if 'page' in query_dict:
                query_dict.pop('page')

            # urlencode将value_list这个字典中的数据转换成 status=1&xx=2 形式
            url = "{}?{}".format(self.request.path_info, query_dict.urlencode())

            tag = '<a class="cell" href="{url}"><input type="checkbox" {ck}><label for="">{text}</label></a>'
            tag = tag.format(url=url, ck=ck, text=text)
            yield mark_safe(tag)


class SelectFilter:
    def __init__(self, name, data_list, request):
        self.name = name
        self.data_list = data_list
        self.request = request

    def __iter__(self):
        yield mark_safe('<select class="select2" multiple="multiple" style="width:100%;">')
        for item in self.data_list:
            key = str(item[0])
            text = item[1]

            selected = ""
            value_list = self.request.GET.getlist(self.name)
            if key in value_list:
                selected = 'selected'
                value_list.remove(key)
            else:
                value_list.append(key)

            # 为自己生成URL，点击时就在后面增加相应的 &xx=1。在当前的URL基础上增加一项
            query_dict = self.request.GET.copy()
            query_dict._mutable = True  # 设置成True才能执行下面的setlist
            query_dict.setlist(self.name, value_list)

            # 如果在100页点击筛选条件，也应回到第一页
            if 'page' in query_dict:
                query_dict.pop('page')

            # urlencode将value_list这个字典中的数据转换成 status=1&xx=2 形式
            url = "{}?{}".format(self.request.path_info, query_dict.urlencode())

            tag = '<option value="{url}" {selected}>{text}</option>'.format(url=url, selected=selected, text=text)
            yield mark_safe(tag)
        yield mark_safe('</select>')


def issues(request, project_id):
    if request.method == 'GET':
        # 根据URL携带的参数做筛选。URL类似：?status=1&status&=2&issues_type=1

        allow_filter_name = ['issues_type', 'status', 'priority', 'assign', 'attention']
        condition = {}
        for name in allow_filter_name:
            value_list = request.GET.get(name)
            if value_list:
                condition['{}__in'.format(name)] = value_list
        queryset = models.Issues.objects.filter(project_id=project_id).filter(**condition)
        # 分页获取数据
        page_object = Pagination(
            current_page=request.GET.get('page'),
            all_count=queryset.count(),
            base_url=request.path_info,
            query_params=request.GET,
            per_page=5,
        )
        issues_obj_list = queryset[page_object.start: page_object.end]

        form = IssuesModelForm(request)

        project_issues_type = models.IssuesType.objects.filter(project_id=project_id).values_list('id', 'title')

        project_total_user = [(request.lxyker.project.creator_id, request.lxyker.project.creator.username)]
        join_user = models.ProjectUser.objects.filter(project_id=project_id).values_list('user_id', 'user__username')
        project_total_user.extend(join_user)

        invite_form = InviteModelForm()

        context = {
            'invite_form': invite_form,
            'form': form,
            'issues_obj_list': issues_obj_list,
            'page_html': page_object.page_html(),
            'filter_list': [
                {'title': '问题类型', 'filter': CheckFilter('issues_type', project_issues_type, request), },
                {'title': '状态', 'filter': CheckFilter('status', models.Issues.status_choices, request), },
                {'title': '优先级', 'filter': CheckFilter('priority', models.Issues.priority_choices, request), },
                {'title': '指派者', 'filter': SelectFilter('assign', project_total_user, request), },
                {'title': '关注者', 'filter': SelectFilter('attention', project_total_user, request), },
            ],
        }
        return render(request, 'web/issues.html', context)

    form = IssuesModelForm(request, data=request.POST)
    if form.is_valid():
        # 数据校验无误
        form.instance.project = request.lxyker.project
        form.instance.creator = request.lxyker.user
        form.save()
        return JsonResponse({'status': True})
    return JsonResponse({'status': False, 'error': form.errors})


def issues_detail(request, project_id, issues_id):
    """编辑问题"""
    issues_object = models.Issues.objects.filter(id=issues_id, project_id=project_id).first()
    form = IssuesModelForm(request, instance=issues_object)
    return render(request, 'web/issues_detail.html', locals())


@csrf_exempt
def issues_record(request, project_id, issues_id):
    """初始化操作记录"""
    if request.method == 'GET':
        reply_list = models.IssuesReply.objects.filter(issues_id=issues_id, issues__project=request.lxyker.project)

        # 将queryset转换为json格式
        data_list = []
        for row in reply_list:
            data = {
                'id': row.id,
                'reply_type_text': row.get_reply_type_display(),
                'content': row.content,
                'creator': row.creator.username,
                'datetime': row.create_datetime.strftime("%Y-%m-%d %H:%M"),
                'parent_id': row.reply_id,
            }
            data_list.append(data)

        return JsonResponse({'status': True, 'data': data_list})

    form = IssuesReplyModelForm(data=request.POST)
    if form.is_valid():
        form.instance.issues_id = issues_id
        form.instance.reply_type = 2
        form.instance.creator = request.lxyker.user
        instance = form.save()

        info = {
            'id': instance.id,
            'reply_type_text': instance.get_reply_type_display(),
            'content': instance.content,
            'creator': instance.creator.username,
            'datetime': instance.create_datetime.strftime("%Y-%m-%d %H:%M"),
            'parent_id': instance.reply_id,
        }

        return JsonResponse({'status': True, 'data': info})
    else:
        return JsonResponse({'status': False, 'error': form.errors})


@csrf_exempt
def issues_change(request, project_id, issues_id):
    issues_object = models.Issues.objects.filter(id=issues_id, project_id=project_id).first()

    post_dict = json.loads(request.body.decode('utf-8'))

    name = post_dict.get('name')
    value = post_dict.get('value')
    field_object = models.Issues._meta.get_field(name)

    def create_reply_record(content):
        new_object = models.IssuesReply.objects.create(
            reply_type=1,
            issues=issues_object,
            content=change_record,
            creator=request.lxyker.user,
        )
        new_reply_dict = {
            'id': new_object.id,
            'reply_type_text': new_object.get_reply_type_display(),
            'content': new_object.content,
            'creator': new_object.creator.username,
            'datetime': new_object.create_datetime.strftime("%Y-%m-%d %H:%M"),
            'parent_id': new_object.reply_id
        }
        return new_reply_dict

    # 1. 数据库字段更新
    # 1.1 文本
    if name in ["subject", 'desc', 'start_date', 'end_date']:
        if not value:
            if not field_object.null:
                return JsonResponse({'status': False, 'error': "您选择的值不能为空"})
            setattr(issues_object, name, None)
            issues_object.save()
            change_record = "{}更新为空".format(field_object.verbose_name)
        else:
            setattr(issues_object, name, value)
            issues_object.save()
            # 记录：xx更为了value
            change_record = "{}更新为{}".format(field_object.verbose_name, value)

        return JsonResponse({'status': True, 'data': create_reply_record(change_record)})

    # 1.2 FK字段（指派的话要判断是否创建者或参与者）
    if name in ['issues_type', 'module', 'parent', 'assign']:
        # 用户选择为空
        if not value:
            # 不允许为空
            if not field_object.null:
                return JsonResponse({'status': False, 'error': "您选择的值不能为空"})
            # 允许为空
            setattr(issues_object, name, None)
            issues_object.save()
            change_record = "{}更新为空".format(field_object.verbose_name)
        else:  # 用户输入不为空
            if name == 'assign':
                # 是否是项目创建者
                if value == str(request.lxyker.project.creator_id):
                    instance = request.lxyker.project.creator
                else:
                    project_user_object = models.ProjectUser.objects.filter(project_id=project_id,
                                                                            user_id=value).first()
                    if project_user_object:
                        instance = project_user_object.user
                    else:
                        instance = None
                if not instance:
                    return JsonResponse({'status': False, 'error': "您选择的值不存在"})

                setattr(issues_object, name, instance)
                issues_object.save()
                change_record = "{}更新为{}".format(field_object.verbose_name, str(instance))  # value根据文本获取到内容
            else:
                # 条件判断：用户输入的值，是自己的值。
                instance = field_object.rel.model.objects.filter(id=value, project_id=project_id).first()
                if not instance:
                    return JsonResponse({'status': False, 'error': "您选择的值不存在"})

                setattr(issues_object, name, instance)
                issues_object.save()
                change_record = "{}更新为{}".format(field_object.verbose_name, str(instance))  # value根据文本获取到内容

        return JsonResponse({'status': True, 'data': create_reply_record(change_record)})

    # 1.3 choices字段
    if name in ['priority', 'status', 'mode']:
        selected_text = None
        for key, text in field_object.choices:
            if str(key) == value:
                selected_text = text
        if not selected_text:
            return JsonResponse({'status': False, 'error': "您选择的值不存在"})

        setattr(issues_object, name, value)
        issues_object.save()
        change_record = "{}更新为{}".format(field_object.verbose_name, selected_text)
        return JsonResponse({'status': True, 'data': create_reply_record(change_record)})

    # 1.4 M2M字段
    if name == "attention":
        # {"name":"attention","value":[1,2,3]}
        if not isinstance(value, list):
            return JsonResponse({'status': False, 'error': "数据格式错误"})

        if not value:  # 没有关注者，value为空列表
            issues_object.attention.set(value)
            issues_object.save()
            change_record = "{}更新为空".format(field_object.verbose_name)
        else:
            # values=["1","2,3,4]  ->   id是否是项目成员（参与者、创建者）
            # 获取当前项目的所有成员
            user_dict = {str(request.lxyker.project.creator_id): request.lxyker.project.creator.username}
            project_user_list = models.ProjectUser.objects.filter(project_id=project_id)
            for item in project_user_list:
                user_dict[str(item.user_id)] = item.user.username
            username_list = []
            for user_id in value:
                username = user_dict.get(str(user_id))
                if not username:
                    return JsonResponse({'status': False, 'error': "用户不存在，请重新设置"})
                username_list.append(username)

            issues_object.attention.set(value)
            issues_object.save()
            change_record = "{}更新为{}".format(field_object.verbose_name, ",".join(username_list))

        return JsonResponse({'status': True, 'data': create_reply_record(change_record)})

    return JsonResponse({'status': False, 'error': "您的输入有误！"})


def invite_url(request, project_id):
    """生成邀请码"""

    form = InviteModelForm(data=request.POST)
    if form.is_valid():
        """
        表单验证通过后：
        1、只有创建者才能邀请 的限制
        2、创建随机邀请码
        3、验证码保存到数据库
        """
        if request.lxyker.user != request.lxyker.project.creator:
            form.add_error('period', '没有权限')
            return JsonResponse({'status': False, 'errors': form.errors})
        random_invite_code = uid(request.lxyker.user.mobile_phone)
        form.instance.project = request.lxyker.project
        form.instance.code = random_invite_code
        form.instance.creator = request.lxyker.user
        form.save()  # 邀请码保存到数据库

        # 邀请码返回给前端
        url = '{scheme}://{host}{path}'.format(
            scheme=request.scheme,
            host=request.get_host(),
            path=reverse('invite_join', kwargs={'code': random_invite_code}),
        )

        return JsonResponse({'status': True, 'data': url})
    return JsonResponse({'status': False, 'error': form.errors})


def invite_join(request, code):
    """点击邀请码后接收邀请"""

    invite_object = models.ProjectInvite.objects.filter(code=code).first()

    if not invite_object:
        return render(request, 'web/invite_join.html', {'error': '邀请码不存在'})

    if invite_object.project.creator == request.lxyker.user:
        return render(request, 'web/invite_join.html', {'error': '项目创建者无需邀请'})

    is_exists = models.ProjectUser.objects.filter(project=invite_object.project, user=request.lxyker.user).exists()
    if is_exists:
        return render(request, 'web/invite_join.html', {'error': '您已经是该项目成员了'})

    # 最多允许的成员（该项目的创建者的价格策略的限制）
    # 根据项目创建者查询最新的一条交易记录，再看这条交易记录是否过期
    max_transaction = models.Transaction.objects.filter(user=invite_object.project.creator).order_by('-id').first()
    if max_transaction.price_policy.category == 1:  # 免费版
        allow_member = max_transaction.price_policy.project_member
    else:
        current_datetime = datetime.datetime.now()
        if max_transaction.end_datetime < current_datetime:
            # 过期，依旧是使用免费版
            free_object = models.PricePolicy.objects.filter(category=1).first()
            allow_member = free_object.project_member
        else:
            # 没有过期
            allow_member = max_transaction.price_policy.project_member

    current_member = models.ProjectUser.objects.filter(project=invite_object.project).count() + 1
    if current_member >= allow_member:
        return render(request, 'web/invite_join.html', {'error': '项目成员数量已达上限，请升级套餐'})

    # 判断邀请码是否过期
    current_datetime = datetime.datetime.now()
    limit_datetime = invite_object.create_datetime + datetime.timedelta(minutes=invite_object.period)
    if current_datetime > limit_datetime:
        return render(request, 'web/invite_join.html', {'error': '邀请链接已失效，请重新邀请'})

    # 邀请码的使用数量限制
    if invite_object.count:
        if invite_object.use_count >= invite_object.count:
            return render(request, 'web/invite_join.html', {'error': '邀请链接使用数量已达上限'})
        invite_object.use_count += 1
        invite_object.save()

    # 走到这里表示应该成功加入这个项目
    models.ProjectUser.objects.create(user=request.lxyker.user, project=invite_object.project)

    invite_object.project.join_count += 1
    invite_object.project.save()

    return render(request, 'web/invite_join.html', {'project': invite_object.project})
