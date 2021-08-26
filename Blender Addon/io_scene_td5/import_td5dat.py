# ##### BEGIN LICENSE BLOCK #####
#
# This program is licensed under Creative Commons BY-NC-SA:
# https://creativecommons.org/licenses/by-nc-sa/3.0/
#
# Created by Dummiesman, 2021
#
# ##### END LICENSE BLOCK #####

import bpy, bmesh
import time, struct, io, math, os

######################################################
# HELPERS
######################################################
def new_material(txnum):
    matname = "TD5Material_" + str(txnum) 
    mtl = bpy.data.materials.new(name=matname)
    mtl["TD5TextureNumber"] = txnum
    
    # basics
    mtl.use_nodes = True
    mtl.use_backface_culling = True
    
    return mtl


def get_or_create_material(txnum):
    matname = "TD5Material_" + str(txnum) 
    mtl = bpy.data.materials.get(matname)
    if mtl is None:
        mtl = new_material(txnum)
    return mtl

def translate_vertex(vertex):
    return (vertex[0] * 0.01,vertex[2] * 0.01 * -1,vertex[1] * 0.01)

def translate_normal(normal):
    return (normal[0] ,normal[2],normal[1] * -1)
    
def translate_uv(uv):
    return (uv[0], 1 - uv[1])
    
######################################################
# IMPORT
######################################################
def import_model(file, obj_name):
    ORIGIN = file.tell()
    
    file.seek(2, 1)
    flag1 = struct.unpack('B', file.read(1))[0]
    file.seek(1, 1)
    
    submesh_count, vertex_count = struct.unpack('<LL', file.read(8))
    radius, cx, cy, cz = struct.unpack('<ffff', file.read(16))
    file.seek(16, 1)
    submesh_offset, vertex_offset, normal_offset = struct.unpack('<LLL', file.read(12))
    has_normals = normal_offset != 0
    file.seek(8, 1)
    
    # submesh descriptors
    # each is tuple of (texture_id, tris, quads)
    file.seek(ORIGIN + submesh_offset, 0)
    submesh_descriptors = []
    for s in range(submesh_count):
        file.seek(2, 1)
        texture_id = struct.unpack('<H', file.read(2))[0]
        file.seek(4, 1)
        tri_count, quad_count = struct.unpack('<HH', file.read(4))
        file.seek(4, 1)
        
        submesh_descriptors.append((texture_id, tri_count, quad_count))
    
    # read vertices
    file.seek(ORIGIN + vertex_offset, 0)
    
    vertices = []
    uvs = []
    normals = []
    colors = []
    
    for c in range(vertex_count):
        x,y,z =  struct.unpack('<fff', file.read(12))
        file.seek(16, 1)
        u,v =  struct.unpack('<ff', file.read(8))
        file.seek(4, 1)
        cr, cg, cb, ca = struct.unpack('<BBBB', file.read(4))
        
        vertices.append(translate_vertex((x,y,z)))
        uvs.append(translate_uv((u,v)))
        colors.append((cr / 255, cg / 255, cb / 255, ca / 255))
        
        
    # read normals
    if has_normals:
        file.seek(ORIGIN + normal_offset, 0)
        for n in range(vertex_count):
            x,y,z =  struct.unpack('<fff', file.read(12))
            file.seek(4, 1)
            normals.append(translate_normal((x,z,y * -1)))
            
    #END OF DATA READ, NOW TRANSLATE TO BLENDER
    # create a Blender object and link it
    scn = bpy.context.scene

    me = bpy.data.meshes.new(obj_name + '_Mesh')
    ob = bpy.data.objects.new(obj_name, me)
    if flag1 != 0:
        # billboard flag, put this object at the position where it will appear in-game
        ob.location = (cx * 0.01,cz * 0.01 * -1,(cy - (radius * 0.65)) * 0.01)
    
    bm = bmesh.new()
    bm.from_mesh(me)
    
    scn.collection.objects.link(ob)
    
    # for merging vertices with the same position and normal
    vertex_remap_table = {}
    remapped_vertices = []
    
    # create layers for this object
    uv_layer = bm.loops.layers.uv.new()
    vc_layer = bm.loops.layers.color.new()
    
    # start adding geometry
    for i in range(vertex_count):
        vx, vy, vz = vertices[i]
        nx, ny, nz = (0,0,0) if not has_normals else normals[i]
        co = (vx, vy, vz)
        normal = (nx, ny, nz)
        
        # add vertex to mesh or remap
        pos_hash = str(co)
        nrm_hash = str(normal)
        vertex_hash = pos_hash + "|" + nrm_hash
        
        if vertex_hash in vertex_remap_table:
            bmvert = remapped_vertices[vertex_remap_table[vertex_hash]]
            remapped_vertices.append(bmvert)
        else:
            # add vertex to mesh
            bmvert = bm.verts.new(co)
            bmvert.normal = normal
            
            # add to tables
            vertex_remap_table[vertex_hash] = len(remapped_vertices)
            remapped_vertices.append(bmvert)
        
    
    # load submeshes
    vertex_offset = 0
    for s in range(submesh_count):
        descriptor = submesh_descriptors[s] # each is tuple of (texture_id, tris, quads)
        tri_count = descriptor[1]
        quad_count = descriptor[2]
        texture_id = descriptor[0]
        
        # make material
        mtl = get_or_create_material(texture_id)
        ob.data.materials.append(mtl)
    
        # make faces
        for tc in range(tri_count):
            vert0 = remapped_vertices[vertex_offset]
            vert1 = remapped_vertices[vertex_offset + 1]
            vert2 = remapped_vertices[vertex_offset + 2]
            
            try:
                face = bm.faces.new((vert0, vert1, vert2))
                face.smooth = True
                face.material_index = s
                
                # set uvs and colors
                face.loops[0][uv_layer].uv = uvs[vertex_offset]
                face.loops[1][uv_layer].uv = uvs[vertex_offset + 1]
                face.loops[2][uv_layer].uv = uvs[vertex_offset + 2]
                
                face.loops[0][vc_layer] = colors[vertex_offset]
                face.loops[1][vc_layer] = colors[vertex_offset + 1]
                face.loops[2][vc_layer] = colors[vertex_offset + 2]
            except Exception as e:
                print(str(e))
                
            vertex_offset += 3
            
        for qc in range(quad_count):
            vert0 = remapped_vertices[vertex_offset]
            vert1 = remapped_vertices[vertex_offset + 1]
            vert2 = remapped_vertices[vertex_offset + 2]
            vert3 = remapped_vertices[vertex_offset + 3]
           
            try:
                face = bm.faces.new((vert0, vert1, vert2, vert3))
                face.smooth = True
                face.material_index = s
                
                # set uvs and colors
                face.loops[0][uv_layer].uv = uvs[vertex_offset]
                face.loops[1][uv_layer].uv = uvs[vertex_offset + 1]
                face.loops[2][uv_layer].uv = uvs[vertex_offset + 2]
                face.loops[3][uv_layer].uv = uvs[vertex_offset + 3]
                
                face.loops[0][vc_layer] = colors[vertex_offset]
                face.loops[1][vc_layer] = colors[vertex_offset + 1]
                face.loops[2][vc_layer] = colors[vertex_offset + 2]
                face.loops[3][vc_layer] = colors[vertex_offset + 3]
            except Exception as e:
                print(str(e))
                  
            vertex_offset += 4

    # calculate normals
    bm.normal_update()
    
    # free resources
    bm.to_mesh(me)
    bm.free()
    
    return
        
######################################################
# IMPORT
######################################################
def load_dat(filepath,
             context):

    print("importing TD5 DAT: %r..." % (filepath))

    time1 = time.perf_counter()
    file = open(filepath, 'rb')
    file_name = os.path.splitext(os.path.basename(filepath))[0]
    
    # import
    import_model(file, file_name)
        
    print(" done in %.4f sec." % (time.perf_counter() - time1))
    
    file.close()


def load(operator,
         context,
         filepath="",
         ):

    load_dat(filepath,
             context,
             )

    return {'FINISHED'}
