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
def import_collision(file, obj_name):
    ORIGIN = file.tell()
    
    scn = bpy.context.scene
    
    positions = []
    strip_index_offsets = [0,0,0,0,-1,0,-1,0,-2,0,0,-1,0,-1,0,-2,0,0,0,0,0,0,0,0]
    
    # read in strip file
    strips_offset, main_strip_count, geo_offset, geo_count, total_strip_count = struct.unpack('<LLLLL', file.read(20))
    
    # read verts table
    file.seek(ORIGIN + geo_offset, 0)
    for x in range(geo_count):
        px, py, pz = struct.unpack('<hhh', file.read(6))
        positions.append((px, py, pz))
        
    
    me = bpy.data.meshes.new(obj_name + '_Mesh')
    ob = bpy.data.objects.new(obj_name, me)
    
    scn.collection.objects.link(ob)
    bpy.context.view_layer.objects.active = ob

    bm = bmesh.new()
    bm.from_mesh(me)
    
    # split info
    split = False
    splitsegoffset = 0
    splitsegnum = 0

    # aaa

    def fill_colseg(type, index0, index2, breadth, offset, pb2):
        #Type 1 = even
        #
        #Type 2 = top right extends + 1 loop
        #Type 3 = top left extends + 1 loop
        #Type 4 = both top ends extend + 1 loop
        #
        #Type 5 = top right shrinks -1 loop
        #Type 6 = top left shrinks - 1 loop
        #Type 7 = both top ends shrink - 1 loop
        #
        #Type 8 = special: split begin
        #Type 9 = special: begin of strip
        #Type 10 = special: end of strip
        #Type 11 = special: split end
        
        # there's probably a better way to do this 
        
        index1 = index0 + breadth + strip_index_offsets[(2*strip_type)]
        index3 = index2 + breadth + strip_index_offsets[(2*strip_type)+1]
        
        verts_a = []
        verts_b = []
        
        for x in range(index0, index1+1):
            pos = positions[x]
            v = bm.verts.new(translate_vertex((pos[0]+offset[0], pos[1]+offset[1], pos[2]+offset[2])))
            verts_a.append(v)
            
        for x in range(index2, index3+1):
            pos = positions[x]
            v = bm.verts.new(translate_vertex((pos[0]+offset[0], pos[1]+offset[1], pos[2]+offset[2])))
            verts_b.append(v)
        
        
        # find our common quad range
        row0_offset= 1 if (type == 6 or type == 7) else 0
        row1_offset= 1 if (type == 3 or type == 4) else 0
        count = breadth
        
        # yeah yeah should be a lookup
        if type == 2 or type == 3 or type == 5 or type == 6:
            count -= 1
        elif type == 4 or type == 7:
            count -= 2
            
        
        # create filler parts
        if type == 3 or type == 4:
            v0 = verts_a[0]
            v1 = verts_b[1]
            v2 = verts_b[0]
            bm.faces.new((v0, v1, v2))
            
        if type == 6 or type == 7:
            v0 = verts_a[0]
            v1 = verts_a[1]
            v2 = verts_b[0]
            bm.faces.new((v0, v1, v2))
            
        # create center quads
        for x in range(count):
            v0 = verts_a[row0_offset + x]
            v1 = verts_a[row0_offset + x + 1]
            
            v2 = verts_b[row1_offset + x]
            v3 = verts_b[row1_offset + x + 1]
            
            face = bm.faces.new((v0, v1, v3, v2))
            face.material_index = 1 if (pb2 & (1 << x)) != 0 else 0
            
            
        # create filler parts
        if type == 2 or type == 4:
            v0 = verts_a[len(verts_a) - 1]
            v1 = verts_b[len(verts_b) - 1]
            v2 = verts_b[len(verts_b) - 2]
            bm.faces.new((v0, v1, v2))
            
        if type == 5 or type == 7:
            v0 = verts_a[len(verts_a) - 2]
            v1 = verts_a[len(verts_a) - 1]
            v2 = verts_b[len(verts_b) - 1]
            bm.faces.new((v0, v1, v2))
    
    print(f"Reading {total_strip_count} strips")
    last_was_end = False # the entry after the end of each strip appears to be garbage?
    for x in range(total_strip_count):
        file.seek(ORIGIN + strips_offset + (24 * x), 0)
    
        strip_type = struct.unpack("<B", file.read(1))[0]
        pad1, materials =  struct.unpack("<BB", file.read(2))
        strip_flags = struct.unpack("<B", file.read(1))[0]
        
        breadth = strip_flags & 0xF
        flagshi = (strip_flags >> 4) & 0xF
        
        index1, index2 = struct.unpack('<HH', file.read(4)) # thing blue, etc
        data1 = struct.unpack('<H', file.read(2))[0]
        data2 = struct.unpack('<H', file.read(2))[0]
        offset = struct.unpack('<lll', file.read(12))
        
        if not last_was_end:
            fill_colseg(strip_type, index1, index2, breadth, offset, materials)
        
        print(f"Processing: {strip_type} | unk byte {pad1} | materials {materials:<08b} | flags {strip_flags} (lower {breadth}, upper {flagshi}) | indices {index1}->{index2} | data1 {data1} | data2 {data2}")
        last_was_end = (strip_type == 10 or x == (main_strip_count - 2))
       
    # merge strips  
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.1)
    
    # free resources
    bm.to_mesh(me)
    bm.free()
    
    
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
    
def import_textures(textures_dir):
    textures_dir_exists = os.path.exists(textures_dir)
    
    if not textures_dir_exists:
        print("Textures directory missing, textures will not be loaded.")
        return

    # load in textures
    print("Loading textures...")
    
    for mat in bpy.data.materials:
        if mat.name.startswith("TD5Material"):
            texnum = mat.name[12:]
            texpath = os.path.join(textures_dir, "texture_" + texnum + ".png")
            if os.path.isfile(texpath):
                img = bpy.data.images.load(texpath)
                
                tex_image_node = mat.node_tree.nodes.new('ShaderNodeTexImage')
                tex_image_node.image = img
                
                bsdf = mat.node_tree.nodes["Principled BSDF"]
                mat.node_tree.links.new(bsdf.inputs['Base Color'], tex_image_node.outputs['Color'])
        
######################################################
# IMPORT
######################################################
def load_dat(filepath,
             context):

    print("Importing TD5 DAT: %r..." % (filepath))

    time1 = time.perf_counter()
    file = open(filepath, 'rb')
    file_name = os.path.splitext(os.path.basename(filepath))[0]
    
    # import
    if "strip.dat" in filepath or "stripb.dat" in filepath:
        import_collision(file, file_name)
    elif "levelinf.dat" in filepath:
        dat_offsets = []
        model_offsets = []
        
        # read group offsets
        models_file = open(filepath.replace("levelinf.dat", "models.dat"), 'rb')
        count = struct.unpack("<L", models_file.read(4))[0]
        
        for x in range(count):
            m_offset = struct.unpack("<L", models_file.read(4))[0]
            dat_offsets.append(m_offset)
            models_file.seek(4, 1) # seek past size
        
        # read model offsets
        for dat_offset in dat_offsets:
            models_file.seek(dat_offset, 0) # seek to model count
            count = struct.unpack('<L', models_file.read(4))[0]
            
            for x in range(count):
                m_offset = struct.unpack('<L', models_file.read(4))[0]
                model_offsets.append(m_offset + dat_offset)
        
        # read models from dat
        for o in model_offsets:
            print("importing from models.dat @ " + str(o))
            models_file.seek(o, 0)
            import_model(models_file, file_name)
        models_file.close()
        
        import_textures(os.path.join(os.path.dirname(filepath) , "textures"))
    else:
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
