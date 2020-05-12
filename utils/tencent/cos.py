from django.conf import settings
from qcloud_cos import CosConfig, CosS3Client, CosServiceError


def create_bucket(bucket, region="ap-beijing"):
    """
    创建桶
    :param bucket: 桶名称
    :param region: 区域
    :return:
    """
    config = CosConfig(Region=region, SecretId=settings.TENCENT_COS_ID, SecretKey=settings.TENCENT_COS_KEY)
    client = CosS3Client(config)
    client.create_bucket(
        Bucket=bucket,
        ACL="public-read"  # private  /  public-read / public-read-write
    )
    # 设置跨域规则
    cors_config = {
        'CORSRule': [
            {
                'AllowedOrigin': '*',
                'AllowedMethod': ['GET', 'PUT', 'HEAD', 'POST', 'DELETE'],
                'AllowedHeader': '*',
                'ExposeHeader': '*',
                'MaxAgeSeconds': 500,
            }
        ]
    }
    client.put_bucket_cors(Bucket=bucket, CORSConfiguration=cors_config)


def upload_file(bucket, region, file_obj, key):
    config = CosConfig(Region=region, SecretId=settings.TENCENT_COS_ID, SecretKey=settings.TENCENT_COS_KEY)
    client = CosS3Client(config)

    response = client.upload_file_from_buffer(
        Bucket=bucket,
        Body=file_obj,
        Key=key,  # 上传到桶之后的文件名
    )
    file_url = "https://{}.cos.{}.myqcloud.com/{}".format(bucket, region, key)
    return file_url


def delete_file(bucket, region, key):
    config = CosConfig(Region=region, SecretId=settings.TENCENT_COS_ID, SecretKey=settings.TENCENT_COS_KEY)
    client = CosS3Client(config)

    response = client.delete_object(
        Bucket=bucket,
        Key=key,
    )


def delete_files(bucket, region, keys):
    config = CosConfig(Region=region, SecretId=settings.TENCENT_COS_ID, SecretKey=settings.TENCENT_COS_KEY)
    client = CosS3Client(config)

    # 批量删除文件
    objects = {
        "Quiet": "true",
        "Object": keys,
    }
    response = client.delete_objects(
        Bucket=bucket,
        Delete=objects
    )


def check_file(bucket, region, key):
    config = CosConfig(Region=region, SecretId=settings.TENCENT_COS_ID, SecretKey=settings.TENCENT_COS_KEY)
    client = CosS3Client(config)

    data = client.head_object(
        Bucket=bucket,
        Key=key,
    )
    return data


def credential(bucket, region):
    """ 获取cos上传临时凭证 """

    from sts.sts import Sts

    config = {
        # 临时密钥有效时长，单位是秒（30分钟=1800秒）
        'duration_seconds': 5,
        # 固定密钥 id
        'secret_id': settings.TENCENT_COS_ID,
        # 固定密钥 key
        'secret_key': settings.TENCENT_COS_KEY,
        # 换成你的 bucket
        'bucket': bucket,
        # 换成 bucket 所在地区
        'region': region,
        # 这里改成允许的路径前缀，可以根据自己网站的用户登录态判断允许上传的具体路径
        # 例子： a.jpg 或者 a/* 或者 * (使用通配符*存在重大安全风险, 请谨慎评估使用)
        'allow_prefix': '*',
        # 密钥的权限列表。简单上传和分片需要以下的权限，其他权限列表请看 https://cloud.tencent.com/document/product/436/31923
        'allow_actions': [
            # "name/cos:PutObject",
            # 'name/cos:PostObject',
            # 'name/cos:DeleteObject',
            # "name/cos:UploadPart",
            # "name/cos:UploadPartCopy",
            # "name/cos:CompleteMultipartUpload",
            # "name/cos:AbortMultipartUpload",
            "*",
        ],

    }

    sts = Sts(config)
    result_dict = sts.get_credential()
    return result_dict


def delete_bucket(bucket, region):
    """删除存储桶"""

    config = CosConfig(Region=region, SecretId=settings.TENCENT_COS_ID, SecretKey=settings.TENCENT_COS_KEY)
    client = CosS3Client(config)

    # 删除桶之前必须得删掉桶中的所有文件

    try:
        while True:
            # 找到桶中的所有文件
            part_objects = client.list_objects(bucket)
            contents = part_objects.get('Contents')
            if not contents:
                break

            objects = {
                'Quiet': 'true',
                'Object': [{'Key': item['Key']} for item in contents],
            }
            # 批量删除
            client.delete_objects(bucket, objects)

        while True:
            # 找到所有碎片并删除
            part_uploads = client.list_multipart_uploads(bucket)
            uploads = part_uploads.get('Upload')
            if not uploads:
                break
            for item in uploads:
                client.abort_multipart_upload(bucket, item['Key'], item['UploadId'])

        client.delete_bucket(bucket)
    except CosServiceError:
        pass