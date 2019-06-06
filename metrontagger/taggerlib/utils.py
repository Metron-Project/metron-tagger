def cleanup_string(path_name):
    path_name = path_name.replace("/", "-")
    path_name = path_name.replace(" :", " -")
    path_name = path_name.replace(": ", " - ")
    path_name = path_name.replace(":", "-")
    path_name = path_name.replace("?", "")

    return path_name
