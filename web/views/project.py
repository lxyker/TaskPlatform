import time

from django.http import JsonResponse
from django.shortcuts import render, redirect

from utils.tencent.cos import create_bucket
from web import models
from web.forms.project import ProjectModelForm


def project_list(request):
    """展示项目列表"""
    if request.method == 'GET':
        # 将 星标的、我创建的、我加入的 项目作为三个列表，整体存入字典中传给前端
        project_dict = {'star': list(), 'mine': list(), 'join': list()}
        create_project_list = models.Project.objects.filter(creator=request.lxyker.user)
        join_project_list = models.ProjectUser.objects.filter(user=request.lxyker.user)
        for row in create_project_list:
            if row.is_star:
                project_dict['star'].append({'type': 'created', 'value': row})
            else:
                project_dict['mine'].append(row)
        for row in join_project_list:
            if row.is_star:
                project_dict['star'].append({'type': 'joined', 'value': row.project})
            else:
                project_dict['join'].append(row)

        form = ProjectModelForm(request)
        return render(request, 'web/project_list.html', locals())
    form = ProjectModelForm(request, data=request.POST)
    if form.is_valid():
        # 填写的创建项目数据没有问题，应该：数据库创建项目、配套存储桶
        # 为项目创建一个桶：
        bucket = '{}-{}-1258158324'.format(request.lxyker.user.mobile_phone, int(time.time()))
        region = 'ap-beijing'
        create_bucket(bucket=bucket, region=region)

        # 项目信息存入数据库
        form.instance.bucket = bucket
        form.instance.region = region
        form.instance.creator = request.lxyker.user
        instance = form.save()

        # 给新创建的项目初始化问题的类型，便于创建问题时有默认的问题类型可选择
        issues_type_object_list = list()
        for item in models.IssuesType.PROJECT_INIT_LIST:
            issues_type_object_list.append(models.IssuesType(project=instance, title=item))
        models.IssuesType.objects.bulk_create(issues_type_object_list)

        return JsonResponse({'status': True})
    else:
        return JsonResponse({'status': False, 'error': form.errors})


def project_star(request, project_type, project_id):
    """将传过来的项目信息查询出来，并星标"""
    if project_type == 'mine':
        models.Project.objects.filter(creator=request.lxyker.user, id=project_id).update(is_star=True)
    elif project_type == 'join':
        models.ProjectUser.objects.filter(user=request.lxyker.user, id=project_id).update(is_star=True)
    return redirect('project_list')


def project_unstar(request, project_type, project_id):
    """将传过来的项目信息查询出来，并取消星标"""
    if project_type == 'created':
        models.Project.objects.filter(creator=request.lxyker.user, id=project_id).update(is_star=False)
    elif project_type == 'joined':
        models.ProjectUser.objects.filter(user=request.lxyker.user, id=project_id).update(is_star=False)
    return redirect('project_list')
