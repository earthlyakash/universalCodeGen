def emptyFunction(file_path, data):
    import os
    # ✍️ Write your custom logic here...
    if not file_path:
        return data

    print(f'Processing: {os.path.basename(file_path)}')
    return data
