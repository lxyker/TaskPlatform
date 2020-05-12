from django import forms

from web import models
from web.forms.bootstrap import BootStrapForm


class WikiModelForm(BootStrapForm, forms.ModelForm):

    class Meta:
        model = models.Wiki
        exclude = ['project', 'depth']

    def __init__(self, request, *args, **kwargs):
        super(WikiModelForm, self).__init__(*args, **kwargs)

        # 解决页面添加Wiki时，显示的 父文章 有其他项目的Wiki    ↓↓
        # 找到想要的字段，把它绑定显示的数据重置：
        # self.fields['parent'].choices = [(1, '选项一'), (2, '选项二')]      # 父文章选择的控制

        total_data_list = [('', '请选择')]
        data_list = models.Wiki.objects.filter(project=request.lxyker.project).values_list('id', 'title')
        total_data_list.extend(data_list)

        self.fields['parent'].choices = total_data_list
