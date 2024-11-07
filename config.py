from typing_extensions import Text

list_field_index = 0
list_field_name = Text
id_field_index = 0

def set_list_field_index(index):
    global list_field_index
    list_field_index = index

def get_list_field_index():
    return list_field_index

def set_list_field_name(name):
    global list_field_name
    list_field_name = name

def get_list_field_name():
    return list_field_name

def set_id_field_index(index):
    global id_field_index
    id_field_index = index

def get_id_field_index():
    return id_field_index
