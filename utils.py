from typing import Any, Callable, Iterable, Optional, TypeVar, cast

import bpy
from bpy.types import Collection, Context, Key, Node, NodeLink, NodeTree, Object

# Cycles types are generated by the python API at runtime, so aren't accessible for static typing https://developer.blender.org/T68050#848508
from cycles.properties import CyclesPreferences, CyclesRenderSettings

T = TypeVar("T")


def apply_suffix(s: Any, suffix: Any) -> str:
    """
    Apply a suffix to a string. Arguments are casted to their string form.

    :param s: The string to suffix.
    :param suffix: The suffix to apply.
    """

    return f"{str(s)}-{str(suffix)}"


def search(
    current: T, is_target: Callable[[T], bool], get_children: Callable[[T], Iterable[T]]
) -> Optional[T]:
    """
    Recursively search a tree-like collection of type `T` for an element of type `T`.

    :param current: The current node being searched.
    :param is_target: A predicate function that returns True when passed the desired element.
    :param gen: A function that returns the direct children of a node when passed a node. The children should be returned as an iterable. This function should not return indirect descendants.
    :returns: the target if it was found, `None` otherwise.
    """

    found = None
    if is_target(current):
        return current
    for item in get_children(current):
        found = search(item, is_target, get_children)
        if found:
            return found
    return found


def copy_collection(src: Collection, dest: Collection, suffix="copy") -> None:
    """
    Recursively copy the contents of the collection src into the collection dest.

    :param src: The collection to copy from.
    :param dest: The collection to copy to.
    :param prefix: A string to suffix the names of copied collections and objects with.
    """

    for obj in cast(Iterable[Object], src.objects):
        obj_dup: Object = obj.copy()
        obj_dup.data = obj.data.copy()
        obj_dup.name = apply_suffix(obj.name, suffix)
        dest.objects.link(obj_dup)

    for coll in cast(Iterable[Collection], src.children):
        coll_dup = bpy.data.collections.new(apply_suffix(coll.name, suffix))
        dest.children.link(coll_dup)
        copy_collection(coll, coll_dup, suffix)


def get_node_of_type(tree: NodeTree, type: str) -> Optional[Node]:
    """
    Get the first node with type `type` from the node tree `tree`.

    :param tree: The tree to search
    :param type: The node type to search for
    :returns: the first node in `tree` with the type `type`, or None if no nodes with the given type could be found
    """

    for node in cast(Iterable[Node], tree.nodes):
        if node.type == type:
            return node
    return None


def configure_cycles(
    context: Context = bpy.context,
    mode: str = "GPU",
    feature_set: str = "SUPPORTED",
    device_type="CUDA",
    samples: int = 4096,
    denoise: bool = True,
) -> None:
    """
    Activate and configure the Cycles rendering engine for rendering.

    :param context: The execution context to configure Cycles for.
    :param mode: The prefered rendering mode. Must be `"GPU"`, `"CPU"` or `"HYBRID"`.
    :param feature_set: The Cycles feature set to use.
    :param device_type: The GPU API to use for rendering. Should be `"CUDA"` or `"OPTIX"`. This will be internally applied as `"CUDA"` if running in `"HYBRID"` mode
    :param samples: The number of samples per frame.
    :param samples: Toggle denoising.
    """

    # Activate Cycles rendering engine
    context.scene.render.engine = "CYCLES"

    # Configure Cycles rendering engine
    cycles_settings: CyclesRenderSettings = context.scene.cycles
    cycles_settings.samples = samples
    cycles_settings.use_denoising = denoise
    if mode == "GPU" or mode == "HYBRID":
        cycles_settings.device = "GPU"
    else:
        cycles_settings.device = "CPU"

    cycles_settings.feature_set = feature_set
    if mode == "GPU":
        cycles_settings.tile_size = 256
    else:
        cycles_settings.tile_size = 16

    cycles_prefs: CyclesPreferences = context.preferences.addons["cycles"].preferences
    if mode == "CPU" or mode == "HYBRID":
        cycles_prefs.compute_device_type = "CUDA"
    else:
        cycles_prefs.compute_device_type = device_type

    #########################################
    # Enable only desired rendering devices #
    #########################################

    # (1) Disable all rendering devices
    for device in cycles_prefs.devices:
        device.use = mode == "HYBRID"
    if mode == "HYBRID":
        return

    # (2) has_active_device() will return True if there is a GPU enabled, so we toggle all devices and test if has_active_device() reports them as a GPU or not.
    devs = []
    for device in cycles_prefs.devices:
        device.use = True
        if (mode == "GPU" and cycles_prefs.has_active_device()) or (
            mode == "CPU" and not cycles_prefs.has_active_device()
        ):
            devs.append(device)
        device.use = False
    # (3) Enable all desired devices
    for dev in devs:
        dev.use = True


def get_link(node: Node, socket_name: str, output: bool = False) -> NodeLink:
    """
    Get the first link from a socket.

    :param node: The node containing the socket.
    :param socket_name: The name of the socket.
    :param output: Should be True if the desired socket is an output socket, False otherwise
    """
    sockets = node.outputs if output else node.inputs
    return sockets[socket_name].links[0]


def find_shape_key_container(obj: Object) -> Optional[Key]:
    """
    Search `bpy.data.shape_keys` to find the Key object containing the Shape Keys for a given object

    :param current: The object who's Shape Keys are being searched for.
    :returns: the Key object if it was found, `None` otherwise.
    """

    for shape_key_container in cast(Iterable[Key], bpy.data.shape_keys):
        if shape_key_container.user == obj.data:
            return shape_key_container
    return None
