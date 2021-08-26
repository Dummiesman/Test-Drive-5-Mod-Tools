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
    matname = "TD6Material_" + str(txnum) 
    mtl = bpy.data.materials.new(name=matname)
    mtl["TD6TextureNumber"] = txnum
    
    # basics
    mtl.use_nodes = True
    mtl.use_backface_culling = True
    
    return mtl


def get_or_create_material(txnum):
    matname = "TD6Material_" + str(txnum) 
    mtl = bpy.data.materials.get(matname)
    if mtl is None:
        mtl = new_material(txnum)
    return mtl

def translate_vertex(vertex):
    return (vertex[0] * 0.01,vertex[2] * 0.01 * -1,vertex[1] * 0.01)

def translate_normal(normal):
    return (normal[0] ,normal[2] * -1 ,normal[1])
    
def translate_uv(uv):
    return (uv[0], 1 - uv[1])
    
######################################################
# IMPORT
######################################################
def import_model(file, obj_name, is_track = False):
    ORIGIN = file.tell()
    
    header = struct.unpack('<H', file.read(2))[0]
    if header != 260:
        raise Exception("Wrong header magic")
    
    flag1 = struct.unpack('B', file.read(1))[0]
    file.seek(1, 1)
    
    submesh_count, total_vert_count = struct.unpack('<LL', file.read(8))
    radius, cx, cy, cz, v4, v5, v6 = struct.unpack('<fffffff', file.read(28))
    file.seek(4, 1)
    
    submesh_offset, vert_offset = struct.unpack('<LL', file.read(8))
    submesh_descriptors = []
    submeshes = []
    
    # read submesh descriptors
    file.seek(ORIGIN + submesh_offset, 0)
    
    for x in range(submesh_count):
        file.seek(2, 1)
        texture_number = struct.unpack('<H', file.read(2))[0]
        file.seek(4, 1)
        vert_count, index_count, svert_offset, index_offset =  struct.unpack('<LLLL', file.read(16))
        submesh_descriptors.append((vert_count, index_count, svert_offset, index_offset, texture_number))
        file.seek(8, 1)
        
    # read submeshes data
    for submesh_descriptor in submesh_descriptors:
        submesh_vert_count = submesh_descriptor[0]
        submesh_vert_offset = submesh_descriptor[2]
        
        submesh_index_count = submesh_descriptor[1]
        submesh_index_offset = submesh_descriptor[3]
        
        # read verts
        file.seek(ORIGIN + submesh_vert_offset, 0)
        
        verts = []
        uvs = []
        colors = [] if is_track else []
        normals = None if is_track else []
        
        for c in range(submesh_vert_count):
            x, y, z = struct.unpack('<fff', file.read(12))
            if is_track:
                file.seek(4, 1)
                cr, cg, cb, ca = struct.unpack('<BBBB', file.read(4))
                colors.append((cr / 255, cg / 255, cb / 255, ca / 255))
                file.seek(4, 1)
            else:
                nx, ny, nz = struct.unpack('<fff', file.read(12))
                normals.append(translate_normal((nx, ny, nz)))
            
            u, v = struct.unpack('<ff', file.read(8))
            
            verts.append(translate_vertex((x,y,z)))
            uvs.append(translate_uv((u,v)))
            
        # read indices
        file.seek(ORIGIN + submesh_index_offset, 0)
        indices = struct.unpack('<{}H'.format(submesh_index_count), file.read(submesh_index_count * 2))
        
        submesh = [verts, uvs, indices, colors, normals]
        submeshes.append(submesh)
    
    
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
    vert_offset = 0
    for ccc in range(submesh_count):
        descriptor = submesh_descriptors[ccc]
        texture_number = descriptor[4]
        
        verts, uvs, indices, colors, normals = submeshes[ccc]
        index_count = len(indices)

        # make material
        mtl = get_or_create_material(texture_number)
        ob.data.materials.append(mtl)
        
        # add verts
        for i in range(len(verts)):
            vx, vy, vz = verts[i]
            nx, ny, nz = (0,0,0) if normals is None else normals[i]
            
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

        # add faces
        for x in range(int(index_count / 3)):
            io = x * 3
            tri_indices = (indices[io + 2], indices[io + 1], indices[io])
            tri_verts = (remapped_vertices[tri_indices[0] + vert_offset], remapped_vertices[tri_indices[1] + vert_offset], remapped_vertices[tri_indices[2] + vert_offset])
            
            try:
                face = bm.faces.new(tri_verts)
                face.smooth = True
                
                face.material_index = ccc
                
                # set uvs and colors
                face.loops[0][uv_layer].uv = uvs[tri_indices[0]]
                face.loops[1][uv_layer].uv = uvs[tri_indices[1]]
                face.loops[2][uv_layer].uv = uvs[tri_indices[2]]
                
                if colors is not None:
                    face.loops[0][vc_layer] = colors[tri_indices[0]]
                    face.loops[1][vc_layer] = colors[tri_indices[1]]
                    face.loops[2][vc_layer] = colors[tri_indices[2]]
            except Exception as e:
                print(str(e))
        
        vert_offset += len(verts)

    # calculate normals
    if is_track:
        bm.normal_update()
    
    # free resources
    bm.to_mesh(me)
    bm.free()
    
    return
        
######################################################
# IMPORT
######################################################
def load_dat(filepath,
             context,
             is_track):

    print("importing TD6 DAT: %r..." % (filepath))

    time1 = time.perf_counter()
    file = open(filepath, 'rb')
    file_name = os.path.splitext(os.path.basename(filepath))[0]
    
    # import
    import_model(file, file_name, is_track)
        
    print(" done in %.4f sec." % (time.perf_counter() - time1))
    
    file.close()


def load(operator,
         context,
         filepath="",
         is_track=False,
         ):

    load_dat(filepath,
             context,
             is_track
             )

    return {'FINISHED'}
