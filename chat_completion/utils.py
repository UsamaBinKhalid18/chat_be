
def get_upload_path(instance, filename):
    return f'files/{instance.uuid}.{filename.split(".")[-1]}'
