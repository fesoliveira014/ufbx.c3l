module smoke;

import std::io::path;
import std::math;
import ufbx;

const double CUBE_HALF_EXTENT = 0.005; // Maya's default 1 cm cube in meters
const double POSITION_TOLERANCE = 1e-6;
const usz CUBE_CORNERS = 36;
const usz CUBE_POSITIONS = 8;

fn String fixture_path(String name) @local {
    Path source = path::tnew($$FILEPATH)!!;
    return (String)source.parent()!!.tappend("../../vendor/ufbx/data", name)!!;
}

fn ufbx::LoadOpts meter_options() @local {
    return {
        .target_axes        = ufbx::axes_right_handed_y_up,
        .target_unit_meters = 1,
        .space_conversion   = ufbx::SpaceConversion.MODIFY_GEOMETRY,
    };
}

fn void test_cube_loads_in_meters() @test {
    ufbx::LoadOpts options = meter_options();
    ufbx::Scene* scene = ufbx::load_file(fixture_path("maya_cube_7400_binary.fbx"), &options)!!;
    defer ufbx::free_scene(scene);

    assert(scene.settings.unit_meters == 0.01);
    assert(scene.nodes.len == 2 && scene.root_node.is_root);
    assert(scene.meshes.len == 1);
    ufbx::Mesh* mesh = scene.meshes[0];
    assert(mesh.num_faces == 6 && mesh.num_triangles == 12 && mesh.material_parts.len == 1);
    foreach (position : mesh.vertex_position.values) {
        foreach (component : position.v) {
            assert(math::abs(component) <= CUBE_HALF_EXTENT + POSITION_TOLERANCE);
        }
    }
    assert(ufbx::axes_right_handed_y_up.up == ufbx::CoordinateAxis.POSITIVE_Y);
}

fn void test_triangulation_and_index_generation() @test {
    ufbx::LoadOpts options = meter_options();
    ufbx::Scene* scene = ufbx::load_file(fixture_path("maya_cube_7400_binary.fbx"), &options)!!;
    defer ufbx::free_scene(scene);
    ufbx::Mesh* mesh = scene.meshes[0];

    uint[6] face_corners;
    assert(ufbx::triangulate_face(face_corners[..], mesh, mesh.faces[0]) == 2);

    float[CUBE_CORNERS * 3] positions;
    uint[CUBE_CORNERS] corner_indices;
    usz corner;
    foreach (face : mesh.faces) {
        uint triangles = ufbx::triangulate_face(face_corners[..], mesh, face);
        for (uint slot = 0; slot < triangles * 3; slot++) {
            ufbx::Vec3 position = mesh.vertex_position.values[mesh.vertex_position.indices[face_corners[slot]]];
            positions[corner * 3] = (float)position.x;
            positions[corner * 3 + 1] = (float)position.y;
            positions[corner * 3 + 2] = (float)position.z;
            corner++;
        }
    }
    assert(corner == CUBE_CORNERS);
    ufbx::VertexStream[1] streams = {
        { .data = &positions, .vertex_count = CUBE_CORNERS, .vertex_size = float::size * 3 },
    };
    assert(ufbx::generate_indices(streams[..], corner_indices[..])!! == CUBE_POSITIONS);
    foreach (index : corner_indices) assert(index < CUBE_POSITIONS);
}

fn void test_bake_runs_on_the_default_stack() @test {
    ufbx::LoadOpts options = meter_options();
    ufbx::Scene* scene = ufbx::load_file(fixture_path("maya_cube_7400_binary.fbx"), &options)!!;
    defer ufbx::free_scene(scene);
    assert(scene.anim_stacks.len == 1);
    ufbx::BakeOpts bake;
    ufbx::BakedAnim* baked = ufbx::bake_anim(scene, scene.anim_stacks[0].anim, &bake)!!;
    ufbx::free_baked_anim(baked);
}

fn void test_missing_file_faults() @test {
    ufbx::LoadOpts options = meter_options();
    if (catch excuse = ufbx::load_file(fixture_path("__missing__.fbx"), &options)) {
        assert(excuse == ufbx::FILE_NOT_FOUND);
    } else {
        assert(false, "expected a fault");
    }
}
