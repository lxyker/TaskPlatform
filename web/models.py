from django.core.validators import RegexValidator
from django.db import models


class UserInfo(models.Model):
    username = models.CharField(verbose_name='用户名', max_length=32, db_index=True)
    email = models.EmailField(verbose_name='邮箱', max_length=64)
    password = models.CharField(verbose_name='密码', max_length=64)
    mobile_phone = models.CharField(verbose_name='手机号', max_length=16,
                                    validators=[RegexValidator(r'^1[3,4,5,6,7,8]\d{9}$')])

    def __str__(self):
        return self.username


class Project(models.Model):
    """项目表"""
    COLOR_CHOICES = [
        (1, "#56b8eb"),
        (2, "#f28033"),
        (3, "#ebc656"),
        (4, "#a2d148"),
        (5, "#20BFA4"),
        (6, "#7461c2"),
        (7, "#20bfa3"),
    ]

    name = models.CharField(verbose_name='项目名', max_length=32)
    color = models.PositiveSmallIntegerField(verbose_name='颜色', choices=COLOR_CHOICES, default=1)
    desc = models.CharField(verbose_name='项目描述', max_length=255, null=True, blank=True)
    use_space = models.PositiveIntegerField(verbose_name='项目已使用空间', default=0, help_text='以B为单位')
    is_star = models.BooleanField(verbose_name='星标', default=False)

    join_count = models.PositiveSmallIntegerField(verbose_name='参与人数', default=1)
    creator = models.ForeignKey(verbose_name='创建者', to='UserInfo')
    create_datetime = models.DateTimeField(verbose_name='创建时间', auto_now_add=True)

    bucket = models.CharField(verbose_name='cos桶', max_length=128)
    region = models.CharField(verbose_name='cos区域', max_length=32)


class ProjectUser(models.Model):
    """项目参与者"""
    user = models.ForeignKey(verbose_name='参与者', to='UserInfo')
    project = models.ForeignKey(verbose_name='项目', to='Project')
    is_star = models.BooleanField(verbose_name='星标', default=False)

    create_datetime = models.DateTimeField(verbose_name='加入时间', auto_now_add=True)


class PricePolicy(models.Model):
    """价格策略表"""
    category_choices = [
        (1, '免费版'),
        (2, '收费版'),
        (3, '其它'),
    ]
    category = models.PositiveSmallIntegerField(verbose_name='收费类型', default=1, choices=category_choices)
    title = models.CharField(verbose_name='标题', max_length=32)
    price = models.PositiveIntegerField(verbose_name='价格')

    project_num = models.PositiveIntegerField(verbose_name='项目数')
    project_member = models.PositiveIntegerField(verbose_name='项目成员数')
    project_space = models.PositiveIntegerField(verbose_name='单项目空间', help_text='以G为单位')
    per_file_size = models.PositiveIntegerField(verbose_name='单文件大小（M）', help_text='以M为单位')

    create_datetime = models.DateTimeField(verbose_name='创建时间', auto_now_add=True)


class Transaction(models.Model):
    """交易记录"""
    status_choice = [
        (1, '未支付'),
        (2, '已支付'),
    ]
    status = models.PositiveSmallIntegerField(verbose_name='状态', choices=status_choice)

    order = models.CharField(verbose_name='订单号', max_length=64, unique=True)
    user = models.ForeignKey(verbose_name='用户', to='UserInfo')
    price_policy = models.ForeignKey(verbose_name='价格策略', to='PricePolicy')

    count = models.PositiveSmallIntegerField(verbose_name='数量（年）', help_text='0表示永久')

    price = models.PositiveIntegerField(verbose_name='实际支付价格')

    start_datetime = models.DateTimeField(verbose_name='开始时间', null=True, blank=True)
    end_datetime = models.DateTimeField(verbose_name='结束时间', null=True, blank=True)

    create_datetime = models.DateTimeField(verbose_name='创建时间', auto_now_add=True)


class Wiki(models.Model):
    project = models.ForeignKey(verbose_name='项目', to='Project')
    title = models.CharField(verbose_name='标题', max_length=32)
    content = models.TextField(verbose_name='内容')

    depth = models.IntegerField(verbose_name='深度', default=1)

    # 自关联
    parent = models.ForeignKey(verbose_name='父文章', to='Wiki', null=True, blank=True, related_name='children')

    def __str__(self):
        return self.title


class FileRepository(models.Model):
    """ 文件库 """
    project = models.ForeignKey(verbose_name='项目', to='Project')
    name = models.CharField(verbose_name='文件夹名称', max_length=32, help_text="文件/文件夹名")
    file_type_choices = [
        (1, '文件'),
        (2, '文件夹'),
    ]
    file_type = models.PositiveSmallIntegerField(verbose_name='类型', choices=file_type_choices)
    file_size = models.PositiveIntegerField(verbose_name='文件大小', null=True, blank=True, help_text='以B为单位')
    parent = models.ForeignKey(verbose_name='父级目录', to='self', related_name='child', null=True, blank=True)
    key = models.CharField(verbose_name='文件储存在COS中的KEY', max_length=128, null=True, blank=True)
    file_path = models.CharField(
        verbose_name='文件路径', max_length=255, null=True, blank=True
    )  # https://桶.cos.ap-beijing/....
    update_user = models.ForeignKey(verbose_name='最近更新者', to='UserInfo')
    update_datetime = models.DateTimeField(verbose_name='更新时间', auto_now=True)


class Issues(models.Model):
    """问题表"""
    project = models.ForeignKey(verbose_name='项目', to='Project')
    issues_type = models.ForeignKey(verbose_name='问题类型', to='IssuesType')

    subject = models.CharField(verbose_name='主题', max_length=64)
    desc = models.TextField(verbose_name='问题描述')
    priority_choices = [
        ("danger", "高"),
        ("warning", "中"),
        ("success", "低"),
    ]
    priority = models.CharField(verbose_name='优先级', max_length=16, choices=priority_choices, default='danger')

    # 新建、处理中、已解决、已忽略、待反馈、已关闭、重新打开
    status_choices = [
        (1, '新建'),
        (2, '处理中'),
        (3, '已解决'),
        (4, '已忽略'),
        (5, '待反馈'),
        (6, '已关闭'),
        (7, '重新打开'),
    ]
    status = models.PositiveSmallIntegerField(verbose_name='状态', choices=status_choices, default=1)

    assign = models.ForeignKey(verbose_name='指派', to='UserInfo', related_name='task', null=True, blank=True)
    attention = models.ManyToManyField(verbose_name='关注者', to='UserInfo', related_name='observe', blank=True)

    start_date = models.DateField(verbose_name='开始时间', null=True, blank=True)
    end_date = models.DateField(verbose_name='结束时间', null=True, blank=True)
    mode_choices = [
        (1, '公开模式'),
        (2, '隐私模式'),
    ]
    mode = models.PositiveSmallIntegerField(verbose_name='模式', choices=mode_choices, default=1)

    parent = models.ForeignKey(verbose_name='父问题', to='self', related_name='child', null=True, blank=True,
                               on_delete=models.SET_NULL)

    creator = models.ForeignKey(verbose_name='创建者', to='UserInfo', related_name='create_problems')

    create_datetime = models.DateTimeField(verbose_name='创建时间', auto_now_add=True)
    latest_update_datetime = models.DateTimeField(verbose_name='最后更新时间', auto_now=True)

    def __str__(self):
        return self.subject


class IssuesType(models.Model):
    """ 问题类型 例如：任务、功能、Bug """
    PROJECT_INIT_LIST = ['任务', '功能', 'bug']

    title = models.CharField(verbose_name='类型名称', max_length=32)
    project = models.ForeignKey(verbose_name='项目', to='Project')

    def __str__(self):
        return self.title


class IssuesReply(models.Model):
    """问题回复"""

    reply_type_choices = [
        (1, '修改记录'),
        (2, '回复'),
    ]
    reply_type = models.PositiveSmallIntegerField(verbose_name='类型', choices=reply_type_choices)

    issues = models.ForeignKey(verbose_name='问题', to='Issues')
    content = models.TextField(verbose_name='描述')
    creator = models.ForeignKey(verbose_name='创建者', to='UserInfo', related_name='create_reply')
    create_datetime = models.DateTimeField(verbose_name='创建时间', auto_now_add=True)

    reply = models.ForeignKey(verbose_name='回复', to='self', null=True, blank=True)


class ProjectInvite(models.Model):
    """项目邀请码"""
    project = models.ForeignKey(verbose_name='项目', to='Project')
    code = models.CharField(verbose_name='邀请码', max_length=64, unique=True)
    count = models.PositiveIntegerField(verbose_name='限制数量', null=True, blank=True, help_text='空表示无数量限制')
    use_count = models.PositiveIntegerField(verbose_name='已邀请数量', default=0)
    period_choices = [
        (30, '30分钟'),
        (60, '1小时'),
        (300, '5小时'),
        (1440, '24小时'),
    ]
    period = models.IntegerField(verbose_name='有效期', choices=period_choices, default=1440)
    create_datetime = models.DateTimeField(verbose_name='创建时间', auto_now_add=True)
    creator = models.ForeignKey(verbose_name='创建者', to='UserInfo', related_name='create_invite')
