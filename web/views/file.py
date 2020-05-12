import json

from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

from utils.tencent.cos import delete_file, delete_files, credential
from web import models
from web.forms.file import FolderModelForm, FileModelForm


def file(request, project_id):
    """展示文件列表&添加文件夹"""
    parent_object = None
    folder_id = request.GET.get('folder', '')
    if folder_id.isdecimal():
        parent_object = models.FileRepository.objects.filter(
            id=int(folder_id),
            file_type=2,
            project=request.lxyker.project,
        ).first()

    # 查看文件列表
    if request.method == 'GET':

        breadcrumb_list = list()
        parent = parent_object
        while parent:
            breadcrumb_list.insert(0, {'id': parent.id, 'name': parent.name})
            parent = parent.parent

        # 获取当前目录下所有的 文件夹+文件
        queryset = models.FileRepository.objects.filter(project=request.lxyker.project).order_by('-file_type')
        if parent_object:
            folder_obj_list = queryset.filter(parent=parent_object)
        else:
            folder_obj_list = queryset.filter(parent__isnull=True)

        form = FolderModelForm(request, parent_object)

        folder_object = parent_object
        return render(request, 'web/file.html', locals())

    # 添加/修改文件夹
    fid = request.POST.get('fid', '')
    edit_object = None
    if fid.isdecimal():
        edit_object = models.FileRepository.objects.filter(id=int(fid), file_type=2,
                                                           project=request.lxyker.project).first()
    if edit_object:
        form = FolderModelForm(request, parent_object, data=request.POST, instance=edit_object)
    else:
        form = FolderModelForm(request, parent_object, data=request.POST)
    if form.is_valid():
        form.instance.project = request.lxyker.project
        form.instance.file_type = 2
        form.instance.update_user = request.lxyker.user
        form.instance.parent = parent_object
        form.save()
        return JsonResponse({'status': True})
    return JsonResponse({'status': False, 'error': form.errors})


def file_delete(request, project_id):
    """删除文件/文件夹"""
    fid = request.GET.get('fid')

    # 级联删除数据库中的值，还需要删除cos中的文件
    will_be_deleted = models.FileRepository.objects.filter(id=fid, project=request.lxyker.project).first()
    if will_be_deleted.file_type == 1:  # 删除的是文件
        # 归还已经使用的空间
        request.lxyker.project.use_space -= will_be_deleted.file_size
        request.lxyker.project.save()

        # cos中删除文件
        delete_file(request.lxyker.project.bucket, request.lxyker.project.region, will_be_deleted.key)

    else:
        # 删除的是文件夹
        total_size = 0
        keys = list()  # 列表中是将要删除的文件的key，且按照cos规定的格式构造

        folder_list = [will_be_deleted, ]
        for folder in folder_list:
            child_list = models.FileRepository.objects.filter(project=request.lxyker.project, parent=folder).order_by(
                '-file_type')
            for child in child_list:
                if child.file_type == 2:
                    folder_list.append(child)
                else:
                    # 统计文件大小
                    total_size += child.file_size

                    # 要删除的文件，加入到keys列表中
                    keys.append({'Key': child.key})  # 按照cos给出的固定格式添加到keys

        # 批量删除cos中的文件
        if keys:
            delete_files(request.lxyker.project.bucket, request.lxyker.project.region, keys)

        if total_size:
            # 归还已经使用的空间
            request.lxyker.project.use_space -= total_size
            request.lxyker.project.save()

    # 级联删除数据库中的文件
    will_be_deleted.delete()

    return JsonResponse({'status': True})


@csrf_exempt
def cos_credential(request, project_id):
    """获取cos上传临时凭证"""
    # 获取每个要上传的文件和大小
    per_file_limit = request.lxyker.price_policy.per_file_size * 1024 ** 2
    total_file_limit = request.lxyker.price_policy.per_file_size * 1024 ** 3

    total_size = 0
    file_list = json.loads(request.body.decode('utf-8'))
    for item in file_list:  # 循环每个文件，判断单个文件大小是否超出限制，计算全部文件大小total_size
        if item['size'] > per_file_limit:
            msg = '文件{}大小超过限制{}M'.format(item['name'], request.lxyker.price_policy.per_file_size)
            return JsonResponse({'status': False, 'error': msg})
        else:
            total_size += item['size']

    # 进行总容量限制
    # request.lxyker.price_policy.project_space  # 项目可用总空间
    # request.lxyker.project.use_space  # 项目已使用的空间

    if request.lxyker.project.use_space + total_size > total_file_limit:
        return JsonResponse({'status': False, 'error': '容量不足，请升级套餐！'})

    data_dict = credential(request.lxyker.project.bucket, request.lxyker.project.region)
    return JsonResponse({'status': True, 'data': data_dict})


@csrf_exempt
def file_post(request, project_id):
    """将已经长传成功的文件写入到数据库"""
    # request.POST.get('name')
    # request.POST.get('size')
    # 前端传递过来的值：
    # name: fileName,
    # file_size: fileSize,
    # key: key,
    # parent: CURRENT_FOLDER_ID,
    # etag: data.ETag,
    # file_path: data.Location

    form = FileModelForm(request, data=request.POST)
    if form.is_valid():
        # form.instance.file_type = 1
        # form.update_user = request.lxyker.user
        # 这种写法，没有办法使用instance.get_file_type_display()获取类型的中文
        # instance = form.save()  # 添加成功后，这个instance就是这个新添加的对象

        # 所以，可用用下面这种自己构造字典的方法，将数据写入数据库，并且将其传递到前端
        # 校验通过，将数据写入到数据库
        data_dict = form.cleaned_data
        data_dict.pop('etag')
        data_dict.update({
            'project': request.lxyker.project,
            'file_type': 1,
            'update_user': request.lxyker.user,
        })
        instance = models.FileRepository.objects.create(**data_dict)

        # 更新项目的已使用空间
        request.lxyker.project.use_space += data_dict['file_size']
        request.lxyker.project.save()

        result = {
            'id': instance.id,
            'name': instance.name,
            'file_size': instance.file_size,
            'username': instance.update_user.username,
            'datetime': instance.update_datetime.strftime('%Y{y}%m{m}%d{d} %H:%m').format(y='年', m='月', d='日'),
            'file_type': instance.get_file_type_display(),
            'download_url': reverse('file_download', kwargs={'project_id': project_id, 'file_id': instance.id})
        }
        return JsonResponse({'status': True, 'data': result})

    return JsonResponse({'status': True, 'data': '文件错误'})


def file_download(request, project_id, file_id):
    """下载文件"""

    # 打开文件，获取文件内容——>去cos中获取文件内容

    import requests

    file_obj = models.FileRepository.objects.filter(id=file_id, project_id=project_id).first()
    res = requests.get(file_obj.file_path)

    # data = res.content()
    data = res.iter_content()  # 文件分块处理：如果要下载的文件比较大

    response = HttpResponse(data)

    # 设置响应头  如果是中文名则需要escape_uri_path转义
    from django.utils.encoding import escape_uri_path
    response['Content-Disposition'] = 'attachment; filename={};'.format(escape_uri_path(file_obj.name))
    return response
