from django.shortcuts import render, redirect

from utils.tencent.cos import delete_bucket
from web import models


def setting(request, project_id):
    return render(request, 'web/setting.html')


def delete(request, project_id):
    if request.method == 'GET':
        return render(request, 'web/setting_delete.html')

    project_name = request.POST.get('project_name')

    if request.lxyker.user != request.lxyker.project.creator:
        return render(request, 'web/setting_delete.html', {'error': '权限不足！'})
    if not project_name or project_name != request.lxyker.project.name:
        return render(request, 'web/setting_delete.html', {'error': '项目名称不正确！'})

    # 执行删除项目操作：1、删除cos中的桶；2、删除数据库中的所有文件
    delete_bucket(request.lxyker.project.bucket, request.lxyker.project.region)
    models.Project.objects.filter(id=project_id).delete()

    return redirect('project_list')