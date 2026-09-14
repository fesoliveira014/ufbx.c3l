module ufbx;

faultdef
    UNKNOWN,
    FILE_NOT_FOUND,
    EMPTY_FILE,
    EXTERNAL_FILE_NOT_FOUND,
    OUT_OF_MEMORY,
    MEMORY_LIMIT,
    ALLOCATION_LIMIT,
    TRUNCATED_FILE,
    IO,
    CANCELLED,
    UNRECOGNIZED_FILE_FORMAT,
    UNINITIALIZED_OPTIONS,
    ZERO_VERTEX_SIZE,
    TRUNCATED_VERTEX_STREAM,
    INVALID_UTF8,
    FEATURE_DISABLED,
    BAD_NURBS,
    BAD_INDEX,
    NODE_DEPTH_LIMIT,
    THREADED_ASCII_PARSE,
    UNSAFE_OPTIONS,
    DUPLICATE_OVERRIDE,
    UNSUPPORTED_VERSION;

<*
 Load an FBX, OBJ or MTL scene from a file.
 @param [&in] options : "Read for the call only."
 @return? FILE_NOT_FOUND, EMPTY_FILE, EXTERNAL_FILE_NOT_FOUND, OUT_OF_MEMORY, MEMORY_LIMIT, ALLOCATION_LIMIT
 @return? TRUNCATED_FILE, IO, CANCELLED, UNRECOGNIZED_FILE_FORMAT, UNINITIALIZED_OPTIONS, INVALID_UTF8
 @return? FEATURE_DISABLED, BAD_NURBS, BAD_INDEX, NODE_DEPTH_LIMIT, THREADED_ASCII_PARSE, UNSAFE_OPTIONS
 @return? DUPLICATE_OVERRIDE, UNSUPPORTED_VERSION, UNKNOWN
 @require path.len > 0
*>
fn Scene*? load_file(String path, LoadOpts* options) {
    Error error;
    Scene* scene = load_file_len(
        filename:     (ZString)path.ptr,
        filename_len: path.len,
        opts:         options,
        error:        &error,
    );
    if (!scene) return error_fault(&error)~;
    return scene;
}

<*
 Bake the animation into linearly interpolated keys.
 @param [&in] scene : "Owns the animation."
 @param [&in] animation : "Usually an anim stack's anim."
 @param [&in] options : "Read for the call only."
 @return? OUT_OF_MEMORY, MEMORY_LIMIT, ALLOCATION_LIMIT, UNINITIALIZED_OPTIONS, BAD_INDEX, UNKNOWN
*>
fn BakedAnim*? bake_anim(Scene* scene, Anim* animation, BakeOpts* options) {
    Error error;
    BakedAnim* baked = bake_anim_raw(scene, animation, options, &error);
    if (!baked) return error_fault(&error)~;
    return baked;
}

<*
 Write the triangle corner indices of one face.
 @param [&in] mesh : "Owns the face."
 @param indices : "Three per triangle of the face."
 @return "Triangle count; zero for a face with fewer than three corners."
 @require face.num_indices < 3 || indices.len >= (usz)(face.num_indices - 2) * 3
*>
fn uint triangulate_face(uint[] indices, Mesh* mesh, Face face) {
    return triangulate_face_raw(indices.ptr, indices.len, mesh, face);
}

<*
 Deduplicate vertex streams in place and write the index buffer.
 @param streams : "Compacted to the unique vertices on success."
 @param indices : "One per input vertex."
 @return "Unique vertex count."
 @return? OUT_OF_MEMORY, ZERO_VERTEX_SIZE, TRUNCATED_VERTEX_STREAM, UNKNOWN
 @require streams.len > 0
*>
fn usz? generate_indices(VertexStream[] streams, uint[] indices) {
    Error error;
    usz vertex_count = generate_indices_raw(
        streams:     streams.ptr,
        num_streams: streams.len,
        indices:     indices.ptr,
        num_indices: indices.len,
        allocator:   null,
        error:       &error,
    );
    if (error.type != ErrorType.NONE) return error_fault(&error)~;
    return vertex_count;
}

fn fault error_fault(Error* error) @private {
    switch (error.type) {
        case NONE:
        case UNKNOWN: return UNKNOWN;
        case FILE_NOT_FOUND: return FILE_NOT_FOUND;
        case EMPTY_FILE: return EMPTY_FILE;
        case EXTERNAL_FILE_NOT_FOUND: return EXTERNAL_FILE_NOT_FOUND;
        case OUT_OF_MEMORY: return OUT_OF_MEMORY;
        case MEMORY_LIMIT: return MEMORY_LIMIT;
        case ALLOCATION_LIMIT: return ALLOCATION_LIMIT;
        case TRUNCATED_FILE: return TRUNCATED_FILE;
        case IO: return IO;
        case CANCELLED: return CANCELLED;
        case UNRECOGNIZED_FILE_FORMAT: return UNRECOGNIZED_FILE_FORMAT;
        case UNINITIALIZED_OPTIONS: return UNINITIALIZED_OPTIONS;
        case ZERO_VERTEX_SIZE: return ZERO_VERTEX_SIZE;
        case TRUNCATED_VERTEX_STREAM: return TRUNCATED_VERTEX_STREAM;
        case INVALID_UTF8: return INVALID_UTF8;
        case FEATURE_DISABLED: return FEATURE_DISABLED;
        case BAD_NURBS: return BAD_NURBS;
        case BAD_INDEX: return BAD_INDEX;
        case NODE_DEPTH_LIMIT: return NODE_DEPTH_LIMIT;
        case THREADED_ASCII_PARSE: return THREADED_ASCII_PARSE;
        case UNSAFE_OPTIONS: return UNSAFE_OPTIONS;
        case DUPLICATE_OVERRIDE: return DUPLICATE_OVERRIDE;
        case UNSUPPORTED_VERSION: return UNSUPPORTED_VERSION;
    }
}
