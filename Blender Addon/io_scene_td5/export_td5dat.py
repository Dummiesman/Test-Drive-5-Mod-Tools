# ##### BEGIN LICENSE BLOCK #####
#
# This program is licensed under Creative Commons BY-NC-SA:
# https://creativecommons.org/licenses/by-nc-sa/3.0/
#
# Created by Dummiesman, 2021
#
# ##### END LICENSE BLOCK #####

import bpy, bmesh
import os, time, struct

import os.path as path

######################################################
# EXPORT FUINCTIONS
######################################################
def translate_vertex(vertex):
    return (vertex[0] / 0.01,vertex[2] / 0.01,vertex[1] / 0.01 * -1)


def translate_normal(normal):
    return (normal[0] ,normal[2],normal[1] * -1)

    
def translate_uv(uv):
    return (uv[0], 1 - uv[1])


def export_object(file, ob, apply_modifiers):
    # create temp mesh
    temp_mesh = None
    if apply_modifiers:
        dg = bpy.context.evaluated_depsgraph_get()
        eval_obj = ob.evaluated_get(dg)
        temp_mesh = eval_obj.to_mesh()
    else:
        temp_mesh = ob.to_mesh()
        
    # get bmesh
    bm = bmesh.new()
    bm.from_mesh(temp_mesh)

    # get and sort triangles
    triangles_unsorted = bm.calc_loop_triangles()
    triangles = []
    triangles_unwrapped = []
   
    triangles_buckets = {}   
    for luple in triangles_unsorted:
        face = luple[0].face
        material_index = face.material_index
        
        bucket = []
        if not material_index in triangles_buckets:
            triangles_buckets[material_index] = bucket
        else:
            bucket = triangles_buckets[material_index]
            
        bucket.append(luple)
        
    for key in sorted(triangles_buckets):
        triangles += triangles_buckets[key]
        
    for luple in triangles:
        triangles_unwrapped += luple
        
    # vars
    uv_layer = bm.loops.layers.uv.active
    vc_layer = bm.loops.layers.color.active
    
    num_materials = len(ob.material_slots)
    
    max_dimension = max(ob.dimensions)
    center = translate_vertex(ob.location)
    
    triangles_loops_len = len(triangles) * 3
    triangles_count = len(triangles)
    
    # calculate offsets
    submesh_offset = 64
    vertex_offset = submesh_offset + (16 * num_materials)
    normals_offset = vertex_offset + (44 * triangles_loops_len)
    
    # header
    file.write(struct.pack('L', 259))
    file.write(struct.pack('LL', num_materials, triangles_loops_len))
    file.write(struct.pack('f', max_dimension))
    file.write(struct.pack('fff', *center))
    file.write(struct.pack('LLLL', 0, 0, 0, 0))
    file.write(struct.pack('LLL', submesh_offset, vertex_offset, normals_offset))
    file.write(struct.pack('LL', 0, 0))
    
    # submeshes
    for submesh in range(num_materials):
        submesh_triangles_count = len(triangles_buckets[submesh])
        material = ob.material_slots[submesh].material
        texnum = submesh
        
        if material is not None and "TD5TextureNumber" in material:
            texnum = int(material["TD5TextureNumber"])
        
        file.write(struct.pack('H', 0))
        file.write(struct.pack('H', texnum))
        file.write(struct.pack('L', 0))
        file.write(struct.pack('HH', submesh_triangles_count, 0))
        file.write(struct.pack('L', 0))
    
    # 'vertices'
    for loop in triangles_unwrapped:
        color = (1,1,1,1)
        uv = (0, 0)
        co = translate_vertex(loop.vert.co)
        
        if uv_layer is not None:
            uv = translate_uv(loop[uv_layer].uv)
        if vc_layer is not None:
            color = loop[vc_layer]
            
        file.write(struct.pack('fff', *co)) # position
        file.write(struct.pack('LLLL', 0, 0, 0, 0)) # unknown
        file.write(struct.pack('ff', *uv)) # uv
        file.write(struct.pack('L', 0)) # unknown
        
        cr = int(max(min(color[0], 1.0), 0.0) * 255)
        cg = int(max(min(color[1], 1.0), 0.0) * 255)
        cb = int(max(min(color[2], 1.0), 0.0) * 255)
        ca = int(max(min(color[3], 1.0), 0.0) * 255)
        file.write(struct.pack('BBBB', cr, cg, cb, ca)) # color
        
    # 'normals'
    for loop in triangles_unwrapped:
        normal = translate_normal(loop.vert.normal)
       
        file.write(struct.pack('fff', *normal))
        file.write(struct.pack('L', 0))
    
    # finish off
    bm.free()
    file.close()
    return

    
######################################################
# EXPORT
######################################################
def save_dat(filepath,
             apply_modifiers,
             context):

    # throw exception if a model isn't selected for exporting
    export_ob = context.view_layer.objects.active
    if export_ob is None:
        raise Exception("Select an object for exporting to the DAT first")
    
    print("Exporting DAT: %r..." % (filepath))
    
    time1 = time.clock()
    file = open(filepath, 'wb')
    
    export_object(file, export_ob, apply_modifiers)
   
    # end write dat file
    print(" done in %.4f sec." % (time.clock() - time1))
    file.close()


def save(operator,
         context,
         filepath="",
         apply_modifiers=False,
         ):
    
    # save DAT
    save_dat(filepath,
             apply_modifiers,
             context,
             )

    return {'FINISHED'}
