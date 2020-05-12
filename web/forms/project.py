from django import forms
from django.core.exceptions import ValidationError

from web import models
from web.forms.bootstrap import BootStrapForm
from web.forms.widgets import ColorRadioSelect


class ProjectModelForm(BootStrapForm, forms.ModelForm):
    bootstrap_class_exclude = ['color']

    class Meta:
        model = models.Project
        fields = ['name', 'color', 'desc']
        widgets = {
            'desc': forms.Textarea,
            'color': ColorRadioSelect(attrs={'class': 'color-radio'}),
        }

    def __init__(self, request, *args, **kwargs):
        super(ProjectModelForm, self).__init__(*args, **kwargs)
        self.request = request

    def clean_name(self):
        name = self.cleaned_data['name']
        is_exists = models.Project.objects.filter(name=name, creator=self.request.lxyker.user).exists()
        if is_exists:
            raise ValidationError('该项目已存在！')

        # 判断项目数量是否超额    ↓↓
        has_created_num = models.Project.objects.filter(creator=self.request.lxyker.user).count()
        if has_created_num >= self.request.lxyker.price_policy.project_num:
            raise ValidationError('可创项目数不足，请升级套餐！')
        return name