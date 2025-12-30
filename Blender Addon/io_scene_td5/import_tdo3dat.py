# ##### BEGIN LICENSE BLOCK #####
#
# This program is licensed under Creative Commons BY-NC-SA:
# https://creativecommons.org/licenses/by-nc-sa/3.0/
#
# Created by Dummiesman, 2021-2025
#
# ##### END LICENSE BLOCK #####

import bpy, bmesh
import time, struct, io, math, os

######################################################
# HELPERS
######################################################
def new_material(txnum):
    matname = "TDO3Material_" + str(txnum) 
    mtl = bpy.data.materials.new(name=matname)
    mtl["TDO3Material_"] = txnum
    
    # basics
    mtl.use_nodes = True
    mtl.use_backface_culling = True
    
    return mtl


def get_or_create_material(txnum):
    matname = "TDO3Material_" + str(txnum) 
    mtl = bpy.data.materials.get(matname)
    if mtl is None:
        mtl = new_material(txnum)
    return mtl

def translate_vertex(vertex):
    return (vertex[0] * -1,vertex[2] * -1,vertex[1])

def translate_normal(normal):
    return (normal[0] * -1 ,normal[2] * -1 ,normal[1])
    
def translate_uv(uv):
    return (uv[0], uv[1])
    
######################################################
# IMPORT
######################################################
def import_model(file, obj_name, is_track):
    ORIGIN = file.tell()
    
    unk_dat_size = 40 if is_track else 44
    unk_dat_size -= 4
    file.seek(unk_dat_size, 1) # unknown data
    
    print(f"reading mtx at {file.tell()}")
    mtx_row0 = translate_normal(struct.unpack('<fff', file.read(12))) # xaxis
    mtx_row1 = translate_normal(struct.unpack('<fff', file.read(12))) # yaxis
    mtx_row2 = translate_normal(struct.unpack('<fff', file.read(12))) # zaxis
    mtx_row3 = translate_vertex(struct.unpack('<fff', file.read(12))) # position
    
    file.seek(12, 1) # unknown data
    
    bbox_min = translate_normal(struct.unpack('<fff', file.read(12)))
    bbox_max = translate_normal(struct.unpack('<fff', file.read(12)))
    
    unk1, unk2 = struct.unpack('<LL', file.read(8))
    print(f"importing mesh @ {ORIGIN}...")
    print(f"unknown mesh values {unk1} {unk2}")
    
    face_count, vert_count = struct.unpack('<LL', file.read(8))
    verts = []
    normals = []
    uvs = []
    face_materials = []
    triangles = []
    
    for x in range(vert_count):
        vert = struct.unpack("<fff", file.read(12))
        verts.append(translate_vertex(vert))
    for x in range(vert_count):
        normal = struct.unpack("<fff", file.read(12))
        normals.append(translate_normal(normal))
    for x in range(vert_count):
        uv = struct.unpack("<ff", file.read(8))
        uvs.append(translate_uv(uv)) 

    for x in range(face_count):
        face_materials.append(struct.unpack("<L", file.read(4))[0]) 
    for x in range(face_count):
        triangles.append(struct.unpack("<LLL", file.read(12))) 
    
    #END OF DATA READ, NOW TRANSLATE TO BLENDER
    # create a Blender object and link it
    scn = bpy.context.scene

    me = bpy.data.meshes.new(obj_name + '_Mesh')
    ob = bpy.data.objects.new(obj_name, me)
    ob.location = mtx_row3
    
    bm = bmesh.new()
    bm.from_mesh(me)
    
    scn.collection.objects.link(ob)
    
    # create layers for this object
    uv_layer = bm.loops.layers.uv.new()
    vc_layer = bm.loops.layers.color.new()
    
    # create materials
    max_mat_idx = max(face_materials)
    for x in range(max_mat_idx+1):
        # make material
        mtl = get_or_create_material(x)
        ob.data.materials.append(mtl)
    
    # start adding geometry
    for x in range(vert_count):
        bm.verts.new(verts[x])
    bm.verts.ensure_lookup_table()
    
    for x in range(face_count):
        try:
            tri_indices = triangles[x]
            verts = (bm.verts[tri_indices[2]], bm.verts[tri_indices[1]], bm.verts[tri_indices[0]])
            face =  bm.faces.new(verts)
            
            face.smooth = True
            face.material_index = face_materials[x]
            
            # set uvs
            face.loops[0][uv_layer].uv = uvs[tri_indices[2]]
            face.loops[1][uv_layer].uv = uvs[tri_indices[1]]
            face.loops[2][uv_layer].uv = uvs[tri_indices[0]]
        except Exception as e:
            print(str(e))
    
    # free resources
    bm.to_mesh(me)
    bm.free()
    
def parse_object(file, obj_name, is_track):
    obj_type = struct.unpack('<L', file.read(4))[0]
    if(obj_type == 0xFFFFFFFF):
        return False # ??
    import_model(file, obj_name, is_track)
    return True
    
def import_track(file, obj_name):
    num_models = struct.unpack('<L', file.read(4))[0]
    mnum = 0

    for x in range(num_models):
        mnum += 1
        print("Importing model " + str(mnum))
        if parse_object(file, obj_name, True):
            file.seek(4, 1)
            
def import_textures(textures_dir,textures_file):
    textures_file_exists = os.path.exists(textures_file)
    if not textures_file_exists:
        print("Textures file missing, textures will not be loaded.")
        return
        
    file = open(textures_file, 'rb')
    num_textures = struct.unpack("<L", file.read(4))[0]
    texture_files = []
    
    for x in range(num_textures):
        file.seek(4, 1) # some kind of type?
        texture_file = file.read(60).decode('ascii').rstrip('\x00')
        print("Texture " + str(len(texture_files)) + ":" + texture_file)
        texture_files.append(texture_file)
    
    # load in textures
    print("Loading textures...")
    
    for mat in bpy.data.materials:
        if mat.name.startswith("TDO3Material"):
            texnum = int(mat.name[13:])
            texpath = os.path.join(textures_dir, texture_files[texnum])
            if os.path.isfile(texpath):
                img = bpy.data.images.load(texpath)
                
                tex_image_node = mat.node_tree.nodes.new('ShaderNodeTexImage')
                tex_image_node.image = img
                
                bsdf = mat.node_tree.nodes["Principled BSDF"]
                mat.node_tree.links.new(bsdf.inputs['Base Color'], tex_image_node.outputs['Color'])
       
    file.close()
    

######################################################
# IMPORT
######################################################
def load_model(filepath,
             context):

    print("importing TDO3 Model: %r..." % (filepath))

    time1 = time.perf_counter()
    file = open(filepath, 'rb')
    file_name = os.path.splitext(os.path.basename(filepath))[0]
    
    # import
    if filepath.lower().endswith(".dmp"):
        parse_object(file, file_name, False)
    elif filepath.lower().endswith(".mp"):
        import_track(file, file_name)
        import_textures(os.path.dirname(filepath), os.path.join(os.path.dirname(filepath), "TEXTURES.REF"))
        
    print(" done in %.4f sec." % (time.perf_counter() - time1))
    
    file.close()


def load(operator,
         context,
         filepath=""
         ):

    load_model(filepath, context)

    return {'FINISHED'}
