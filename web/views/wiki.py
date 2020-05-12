from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

from utils.encrypt import uid
from utils.tencent.cos import upload_file
from web import models
from web.forms.wiki import WikiModelForm


def wiki(request, project_id):
    """wiki首页"""
    wiki_id = request.GET.get('wiki_id')
    if not wiki_id or not wiki_id.isdecimal():  # 若 不存在 或 不合法
        return render(request, 'web/wiki.html')
    wiki_obj = models.Wiki.objects.filter(id=wiki_id, project_id=project_id).first()
    return render(request, 'web/wiki.html', locals())


def wiki_add(request, project_id):
    """增加wiki文章"""
    if request.method == 'GET':
        form = WikiModelForm(request)
        return render(request, 'web/wiki_form.html', locals())
    form = WikiModelForm(request, data=request.POST)
    if form.is_valid():

        # 这篇文章的深度：如果有父深度，那么在父深度上加1；无父深度，表明深度为1
        form.instance.depth = form.instance.parent.depth + 1 if form.instance.parent else 1

        # 用户没有填写project_id，需要我们自己传入保存
        form.instance.project = request.lxyker.project
        form.save()

        url = reverse('wiki', kwargs={'project_id': project_id})
        return redirect(url)
    return render(request, 'web/wiki_form.html', locals())


def wiki_catalog(request, project_id):
    """wiki目录展示"""
    data = models.Wiki.objects.filter(project=request.lxyker.project).values(
        'id', 'title', 'parent_id').order_by('depth', 'id')
    return JsonResponse({'status': True, 'data': list(data)})


def wiki_delete(request, project_id, wiki_id):
    models.Wiki.objects.filter(project=request.lxyker.project, id=wiki_id).delete()
    url = reverse('wiki', kwargs={'project_id': project_id})
    return redirect(url)


def wiki_edit(request, project_id, wiki_id):
    wiki_obj = models.Wiki.objects.filter(project=request.lxyker.project, id=wiki_id).first()
    if not wiki_obj:
        url = reverse('wiki', kwargs={'project_id': project_id})
        return redirect(url)
    if request.method == 'GET':
        form = WikiModelForm(request, instance=wiki_obj)
        return render(request, 'web/wiki_form.html', locals())
    form = WikiModelForm(request, data=request.POST, instance=wiki_obj)
    if form.is_valid():
        # 这篇文章的深度：如果有父深度，那么在父深度上加1；无父深度，表明深度为1
        form.instance.depth = form.instance.parent.depth + 1 if form.instance.parent else 1
        form.save()

        url = reverse('wiki', kwargs={'project_id': project_id})
        return redirect(url)
    return render(request, 'web/wiki_form.html', locals())


@csrf_exempt
def wiki_upload(request, project_id):
    """MarkDown上传图片"""
    result = {
        'success': 0,
        'message': None,
        'url': None,
    }
    image_object = request.FILES.get('editormd-image-file')
    if not image_object:
        result['message'] = '文件不存在'
        return JsonResponse(result)
    suffix_name = image_object.name.rsplit('.')[-1]
    img_cos_name = '{}.{}'.format(uid(request.lxyker.user.mobile_phone), suffix_name)

    image_url = upload_file(
        bucket=request.lxyker.project.bucket,
        region=request.lxyker.project.region,
        file_obj=image_object,
        key=img_cos_name,
    )
    result['success'] = 1
    result['url'] = image_url
    return JsonResponse(result)