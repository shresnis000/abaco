"""Module to determine file system mounts for an actor."""

from common.config import conf

from common.logs import get_logger
logger = get_logger(__name__)


def replace_tokens(s, actor):
    """Replaces the following tokens in a string based on a dictionary representing an actor:
         tenant_id: the tenant id associated with the actor.
         username: the username of the owner of the actor.
         tasdir: the homeDirectory attribute returned from tas. This attribute requires the
                            use_tas_uid config must be set to true.
    """
    logger.debug(f"top of replace_tokens for string: {s}")
    s = s.replace('{username}', actor['owner'])
    s = s.replace('{tenant_id}', actor['tenant'])
    if '{tasdir}' in s:
        if 'tasdir' in actor and type(actor['tasdir']) == str:
            logger.debug(f"tasdir in actor is a string, value: {actor['tasdir']}. attempting to replace tasdir from string s: {s}")
            s = s.replace('{tasdir}', actor['tasdir'])
        else:
            logger.error("actor did not have a tasdir string though "
                         "there is one in the mounts string. s: {}. actor: {}".format(s, actor))
            # better to return an empty string in this case:
            return ''
    return s


def process_mount_strs(mount_strs, actor):
    """Process the mount_strs list including token replacement for recognized attributes."""
    result = []
    if not mount_strs:
        return result
    #mounts = mount_strs.split(",")
    mounts = mount_strs
    for m in mounts:
        parts = m.split(":")
        if not len(parts) == 3:
            # we will "swallow" invalid global_mounts config since this is not something the user can fix;
            # however, we log an error:
            logger.error("Invalid global_mounts config. "
                         "Each config must be two paths and a format separated by a colon: {}".format(m))
        else:
            host_path = replace_tokens(parts[0], actor)
            container_path = replace_tokens(parts[1], actor)
            mode = parts[2]
            if host_path == '' or container_path == '':
                logger.info("skipping mount due to empty string. "
                            "host_path: {}. container_path: {}".format(host_path, container_path))
            else:
                result.append({'host_path': host_path,
                               'container_path': container_path,
                               'mode': mode})
    logger.info(f"Returning global mounts: {result}")
    return result


def get_global_mounts(actor):
    """
    Read and parse the global_mounts configs.
    Returns a list of dictionaries containing host_path, container_path and mode.
    """
    # first look for a tenant-specific global_mounts config:
    tenant = actor['tenant'].lower()
    
    tenant_tenant_object = conf.get(f"{tenant}_tenant_object") or {}
    mount_strs = tenant_tenant_object.get("global_mounts") or conf.global_tenant_object.get("global_mounts") or None
    if not mount_strs:
        logger.info("No workers.global_mounts config. Skipping.")
    return process_mount_strs(mount_strs, actor)


def get_privileged_mounts(actor):
    """
    Read and parse the global_mounts config.
    Returns a list of dictionaries containing host_path, container_path and mode.
    """
    mount_strs = conf.worker_privileged_mounts or None
    if not mount_strs:
        logger.info("No workers.privileged_mounts config. Skipping.")
    return process_mount_strs(mount_strs, actor)


def get_all_mounts(actor):
    """Get all mounts for a given actor description, actor. This function is called at registration
    time to set the mounts parameter for the actor.
    """
    # get the global mounts first and then get the privileged mounts so that privileged mounts overlay.
    logger.debug(f"top of get_all_mounts for actor: {actor}")
    result = get_global_mounts(actor)
    logger.debug(f"just got the global mounts: {result}")
    if actor.get('privileged'):
        logger.debug(f"getting the privileged mounts for actor: {actor}")
        result.extend(get_privileged_mounts(actor))
    logger.debug(f"final mounts: {result}")
    return result
