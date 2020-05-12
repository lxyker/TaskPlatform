from django import forms

from web import models
from web.forms.bootstrap import BootStrapForm


class IssuesModelForm(BootStrapForm, forms.ModelForm):
    class Meta:
        model = models.Issues
        exclude = ['project', 'creator', 'create_datetime', 'latest_update_datetime']
        widgets = {
            'assign': forms.Select(attrs={'class': 'selectpicker', 'data-live-search': 'true'}),
            'parent': forms.Select(attrs={'class': 'selectpicker', 'data-live-search': 'true'}),
            'attention': forms.SelectMultiple(
                attrs={'class': 'selectpicker', 'data-live-search': 'true', 'data-actions-box': 'true'},
            ),
            "start_date": forms.DateTimeInput(attrs={'autocomplete': "off"}),
            "end_date": forms.DateTimeInput(attrs={'autocomplete': "off"}),
        }

    def __init__(self, request, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 1、获取当前项目的所有问题类型
        issue_types = models.IssuesType.objects.filter(project=request.lxyker.project).values_list('id', 'title')
        self.fields['issues_type'].choices = issue_types

        # 2、处理指派和关注者
        # 到数据库中找到当前项目的参与者和创建者
        total_user_list = [(request.lxyker.project.creator_id, request.lxyker.project.creator.username,)]
        project_user_list = models.ProjectUser.objects.filter(project=request.lxyker.project).values_list('user_id',
                                                                                                          'user__username')

        total_user_list.extend(project_user_list)

        self.fields['assign'].choices = total_user_list
        self.fields['attention'].choices = total_user_list

        # 3、找到当前项目已经创建的问题
        parent_list = [('', '未选中任何项'), ]
        parent_object_list = models.Issues.objects.filter(project=request.lxyker.project).values_list('id', 'subject')
        parent_list.extend(parent_object_list)
        self.fields['parent'].choices = parent_list


class IssuesReplyModelForm(forms.ModelForm):
    class Meta:
        model = models.IssuesReply
        fields = ['content', 'reply']


class InviteModelForm(BootStrapForm, forms.ModelForm):
    class Meta:
        model = models.ProjectInvite
        fields = ['period', 'count']
