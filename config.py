from typing_extensions import Text

segments_field_index = 0
segments_field_name = Text
id_field_index = 0

def set_segments_field_index(index):
    global segments_field_index
    segments_field_index = index

def get_segments_field_index():
    return segments_field_index

def set_segments_field_name(name):
    global segments_field_name
    segments_field_name = name

def get_segments_field_name():
    return segments_field_name

def set_id_field_index(index):
    global id_field_index
    id_field_index = index

def get_id_field_index():
    return id_field_index
