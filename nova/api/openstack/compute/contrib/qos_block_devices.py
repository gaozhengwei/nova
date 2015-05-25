# Copyright 2014 letv.com
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from webob import exc

from nova.api.openstack import extensions
from nova import compute
from nova import db
from nova import exception
from nova.objects import block_device as block_device_obj
from nova.openstack.common.gettextutils import _
from nova.openstack.common import log as logging
from nova.openstack.common import uuidutils

LOG = logging.getLogger(__name__)
authorize_index = extensions.extension_authorizer('compute',
                                                  'qos_block_devices:index')
authorize_update = extensions.extension_authorizer('compute',
                                                   'qos_block_devices:update')

MIN_BINDWIDTH = 1 * 1024 * 1024
MIN_IOPS = 10


class QoSBlockDeviceController(object):
    """The block device QoS API controller for the OpenStack API."""

    def __init__(self):
        super(QoSBlockDeviceController, self).__init__()
        self.compute_api = compute.API()

    def _check_bandwidth_param(self, value):
        try:
            value = int(value)
        except ValueError:
            msg = _("%s should be an integer") % value
            raise exc.HTTPBadRequest(explanation=msg)

        if value < 0:
            msg = _("Qos value should not be negative.")
            raise exc.HTTPBadRequest(explanation=msg)
        if value > 0 and value < MIN_BINDWIDTH:
            msg = _("Disk I/O bandwidth should not less than %s "
                    "MBps.") % (MIN_BINDWIDTH / 1024 / 1024)
            raise exc.HTTPBadRequest(explanation=msg)

        return value

    def _check_iops_param(self, value):
        try:
            value = int(value)
        except ValueError:
            msg = _("%s should be an integer") % value
            raise exc.HTTPBadRequest(explanation=msg)

        if value < 0:
            msg = _("Qos value should not be negative.")
            raise exc.HTTPBadRequest(explanation=msg)
        if value > 0 and value < MIN_IOPS:
            msg = _("Disk IOPS should not less than %s.") % MIN_IOPS
            raise exc.HTTPBadRequest(explanation=msg)

        return value

    def _get_qos_from_body(self, body):
        if 'qos_block_device' not in body:
            msg = _("Missing 'qos_block_device' in the request body")
            raise exc.HTTPBadRequest(explanation=msg)
        qos = {}
        qos_req = body['qos_block_device']
        qos_bandwidth_keys = ['total_bps', 'read_bps', 'write_bps']
        qos_iops_keys = ['total_iops', 'read_iops', 'write_iops']

        for key in qos_bandwidth_keys:
            if key in qos_req:
                value = self._check_bandwidth_param(qos_req[key])
                qos[key] = value

        for key in qos_iops_keys:
            if key in qos_req:
                value = self._check_iops_param(qos_req[key])
                qos[key] = value

        return qos

    def update(self, req, id, server_id, body):
        context = req.environ['nova.context']
        authorize_update(context)

        try:
            bdm_id = int(id)
        except ValueError:
            msg = _("Block device mapping id should be an integer")
            raise exc.HTTPBadRequest(explanation=msg)

        if not uuidutils.is_uuid_like(server_id):
            msg = _("Server id should be a uuid")
            raise exc.HTTPBadRequest(explanation=msg)

        try:
            instance = self.compute_api.get(
                context, server_id, want_objects=True)
        except exception.InstanceNotFound as e:
            raise exc.HTTPNotFound(explanation=e.format_message())

        bdms = db.block_device_mapping_get_all_by_instance(
            context, instance['uuid'])

        existFlag = False
        for bdm in bdms:
            if bdm_id == bdm['id']:
                device_name = bdm['device_name']
                existFlag = True

        if True != existFlag:
            msg = _("Could not found block device %(bdm_id)s for"
                    " instance %(instance_uuid)s") % dict(bdm_id=bdm_id,
                                            instance_uuid=instance['uuid'], )
            raise exc.HTTPNotFound(explanation=msg)

        qos = self._get_qos_from_body(body)
        try:
            qos_ref = db.block_device_qos_get_by_block_device_mapping_id(
                context, bdm_id)
        except exception.BlockDeviceQoSNotFoundForBDM as e:
            raise exc.HTTPNotFound(explanation=e.format_message())

        #check args
        argconflictflag = False
        if 'total_bps' in qos:
            if 'read_bps' in qos:
                if ((0 != qos['total_bps']) and (0 != qos['read_bps'])):
                    argconflictflag = True
            if 'write_bps' in qos:
                if ((0 != qos['total_bps']) and (0 != qos['write_bps'])):
                    argconflictflag = True

        if 'total_iops' in qos:
            if 'read_iops' in qos:
                if ((0 != qos['total_iops']) and (0 != qos['read_iops'])):
                    argconflictflag = True
            if 'write_iops' in qos:
                if ((0 != qos['total_iops']) and (0 != qos['write_iops'])):
                    argconflictflag = True

        if True == argconflictflag:
            msg = _("total and read/write cannot be set at the same time!")
            raise exc.HTTPBadRequest(explanation=msg)

        # if total has been set and want to set write/read,
        # total will be cleared.
        if (0 != qos_ref['total_bps']):
            if ((('read_bps' in qos) and (0 != qos['read_bps'])) or
               (('write_bps' in qos) and (0 != qos['write_bps']))):
                qos['total_bps'] = 0

        if (0 != qos_ref['total_iops']):
            if ((('read_iops' in qos) and (0 != qos['read_iops'])) or
               ((('write_iops' in qos) and (0 != qos['write_iops'])))):
                qos['total_iops'] = 0

        # if read/write has been set and want to set total,
        # read/write will be cleared.
        if ((0 != qos_ref['read_bps'] or 0 != qos_ref['write_bps']) and
           (('total_bps' in qos) and (0 != qos['total_bps']))):
            qos['read_bps'] = 0
            qos['write_bps'] = 0

        if ((0 != qos_ref['read_iops'] or 0 != qos_ref['write_iops']) and
           (('total_iops' in qos) and (0 != qos['total_iops']))):
            qos['read_iops'] = 0
            qos['write_iops'] = 0

        self.compute_api.update_block_device_qos(
            context, instance, bdm_id, qos)

        keys = ['total_bps', 'total_iops', 'read_bps', 'write_bps',
                'read_iops', 'write_iops',
                'block_device_mapping_id', 'id', ]
        result = dict((key, qos_ref[key]) for key in keys)
        result.update(qos)

        result['device_name'] = device_name
        return {'qos_block_device': result, }

    def index(self, req, server_id):
        context = req.environ['nova.context']
        authorize_index(context)

        if not uuidutils.is_uuid_like(server_id):
            msg = _("Server id should be a uuid")
            raise exc.HTTPBadRequest(explanation=msg)

        try:
            instance = self.compute_api.get(
                context, server_id, want_objects=True)
        except exception.InstanceNotFound as e:
            raise exc.HTTPNotFound(explanation=e.format_message())

        bdms = block_device_obj.BlockDeviceMappingList.get_by_instance_uuid(
            context, instance['uuid'])
        result = []
        for bdm in bdms:
            try:
                qos_ref = db.block_device_qos_get_by_block_device_mapping_id(
                    context, bdm['id'])
            except exception.BlockDeviceQoSNotFoundForBDM as e:
                continue

            qos_keys = ['total_bps', 'total_iops', 'read_bps', 'write_bps',
                        'read_iops', 'write_iops']
            qos = dict((key, qos_ref[key]) for key in qos_keys)
            qos['block_device_mapping_id'] = qos_ref['block_device_mapping_id']
            qos['id'] = qos_ref['id']
            qos['device_name'] = bdm['device_name']
            result.append(qos)

        return {'qos_block_devices': result, }


class Qos_block_devices(extensions.ExtensionDescriptor):
    """Block device QoS management extension."""
    name = "QoSBlockDevices"
    alias = "os-qos-block-devices"
    namespace = ("http://docs.openstack.org/compute/ext/"
                 "qos-block-devices/api/v2")
    updated = "2014-06-13T00:00:00+00:00"

    def get_resources(self):
        res = extensions.ResourceExtension('os-qos-block-devices',
                                           QoSBlockDeviceController(),
                                           parent=dict(
                                               member_name='server',
                                               collection_name='servers'))
        return [res]
