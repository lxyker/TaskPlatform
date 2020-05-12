import hashlib
import uuid

from django.conf import settings


def md5(string):
    """用md5给字符串加密"""
    # 用django的SECRET_KEY作为盐
    hash_obj = hashlib.md5(settings.SECRET_KEY.encode('utf-8'))
    hash_obj.update(string.encode('utf-8'))
    return hash_obj.hexdigest()

def uid(string):
    """给图片设置随机字符串名称"""
    data = '{}-{}'.format(str(uuid.uuid4()), string)
    return md5(data)