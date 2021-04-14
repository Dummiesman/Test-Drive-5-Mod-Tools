# ##### BEGIN LICENSE BLOCK #####
#
# This program is licensed under Creative Commons BY-NC-SA:
# https://creativecommons.org/licenses/by-nc-sa/3.0/
#
# Created by Dummiesman, 2021
#
# ##### END LICENSE BLOCK #####

bl_info = {
    "name": "Test Drive 5",
    "author": "Dummiesman",
    "version": (0, 0, 1),
    "blender": (2, 90, 1),
    "location": "File > Import-Export",
    "description": "Import/Export Test Drive 5 files",
    "warning": "",
    "doc_url": "https://github.com/Dummiesman/Test-Drive-5-Mod-Tools/",
    "tracker_url": "https://github.com/Dummiesman/Test-Drive-5-Mod-Tools/",
    "support": 'COMMUNITY',
    "category": "Import-Export"}

import os
import bpy

from bpy.props import (
        BoolProperty,
        EnumProperty,
        FloatProperty,
        StringProperty,
        CollectionProperty,
        )

from bpy_extras.io_utils import (
        ImportHelper,
        ExportHelper,
        )


class ImportTD5Level(bpy.types.Operator, ImportHelper):
    """Import an entire level from Test Drive 5"""
    bl_idname = "import_scene.td5level"
    bl_label = 'Import Test Drive 5 Level'
    bl_optoins = {'UNDO'}
    
    filename_ext = "*"
    filter_glob: StringProperty(default="*", options={'HIDDEN'})
    
    def execute(self, context):
        selected_dir = self.filepath
        if not os.path.isdir(selected_dir) and os.path.isfile(selected_dir):
            selected_dir = os.path.dirname(os.path.abspath(self.filepath))
        
        models_dir = os.path.join(selected_dir, "models")
        textures_dir = os.path.join(selected_dir, "textures")
        textures_dir_exists = os.path.exists(textures_dir)
        
        if not os.path.exists(models_dir):
            raise Exception("Models directory does not exist within this level direectory. Please run td5unpack on the models.dat file, and optionally the textures.dat file.")
        if not textures_dir_exists:
            print("Textures directory missing, textures will not be loaded.")
            
        print("Importing level " + selected_dir)
        print("Importing models...")
        
        # import models
        file_list = sorted(os.listdir(models_dir))
        obj_list = [item for item in file_list if item.endswith('.dat')]

        for item in obj_list:
            path_to_file = os.path.join(models_dir, item)
            bpy.ops.import_mesh.td5dat(filepath = path_to_file)
            
        # load in textures
        if textures_dir_exists:
            print("Loading textures...")
            
            for mat in bpy.data.materials:
                if mat.name.startswith("TD5Material"):
                    texnum = mat.name[12:]
                    texpath = os.path.join(textures_dir, "texture_" + texnum + ".png")
                    img = bpy.data.images.load(texpath)
                    
                    tex_image_node = mat.node_tree.nodes.new('ShaderNodeTexImage')
                    tex_image_node.image = img
                    
                    bsdf = mat.node_tree.nodes["Principled BSDF"]
                    mat.node_tree.links.new(bsdf.inputs['Base Color'], tex_image_node.outputs['Color'])
         
        print("Level import complete")
        return {'FINISHED'}
    

class ImportTD5DAT(bpy.types.Operator, ImportHelper):
    """Import from Test Drive 5 file format (.dat)"""
    bl_idname = "import_mesh.td5dat"
    bl_label = 'Import Test Drive 5 DAT'
    bl_options = {'UNDO'}

    filename_ext = ".dat"
    filter_glob: StringProperty(default="*.dat;*.prr", options={'HIDDEN'})

    def execute(self, context):
        from . import import_td5dat
        keywords = self.as_keywords(ignore=("axis_forward",
                                            "axis_up",
                                            "filter_glob",
                                            "check_existing",
                                            ))

        return import_td5dat.load(self, context, **keywords)

class ExportTD5DAT(bpy.types.Operator, ExportHelper):
    """Export to Test Drive 5 file format (.dat)"""
    bl_idname = "export_mesh.td5dat"
    bl_label = 'Export Test Drive 5 DAT'

    filename_ext = ".dat"
    filter_glob: StringProperty(
            default="*.dat",
            options={'HIDDEN'},
            )

    apply_modifiers: BoolProperty(
        name="Apply Modifiers",
        description="Do you desire modifiers to be applied in the exported file?",
        default=True,
        )
        
    def execute(self, context):
        from . import export_td5dat
        
        keywords = self.as_keywords(ignore=("axis_forward",
                                            "axis_up",
                                            "filter_glob",
                                            "check_existing",
                                            ))
                                    
        return export_td5dat.save(self, context, **keywords)

# Add to a menu
def menu_func_export_dat(self, context):
    self.layout.operator(ExportTD5DAT.bl_idname, text="Test Drive 5 (.dat)")
    
def menu_func_import_dat(self, context):
    self.layout.operator(ImportTD5DAT.bl_idname, text="Test Drive 5 (.dat)")
    
def menu_func_import_level(self, context):
    self.layout.operator(ImportTD5Level.bl_idname, text="Test Drive 5 Level")


# Register factories
def register():
    bpy.utils.register_class(ImportTD5DAT)
    bpy.utils.register_class(ImportTD5Level)
    bpy.utils.register_class(ExportTD5DAT)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import_dat)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import_level)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export_dat)


def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export_dat)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import_level)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import_dat)
    bpy.utils.unregister_class(ExportTD5DAT)
    bpy.utils.unregister_class(ImportTD5Level)
    bpy.utils.unregister_class(ImportTD5DAT)


if __name__ == "__main__":
    register()
