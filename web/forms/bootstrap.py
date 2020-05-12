class BootStrapForm:
    bootstrap_class_exclude = []

    def __init__(self, *args, **kwargs):
        super(BootStrapForm, self).__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name in self.bootstrap_class_exclude:
                pass
            else:
                field.widget.attrs['class'] = 'form-control'
                field.widget.attrs['placeholder'] = '请输入{}'.format(field.label)