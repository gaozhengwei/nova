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

import contextlib

import mock
from webob import exc

from nova.api.openstack.compute.contrib import qos_block_devices
from nova import db
from nova import exception
from nova.objects import block_device as block_device_obj
from nova import test
from nova.tests.api.openstack import fakes


class QoSBlockDeviceTest(test.NoDBTestCase):

    def setUp(self):
        super(QoSBlockDeviceTest, self).setUp()
        self.controller = qos_block_devices.QoSBlockDeviceController()

    def _make_index_req(self, use_admin_context=False):
        return fakes.HTTPRequest.blank(
            '/v2/fake/servers/8ab0e5b9-d87a-457e-ae58-9f4bb22e8c3d'
            '/os-qos-block-devices',
            use_admin_context=use_admin_context)

    def test_get_works(self):
        instance = {'uuid': '8ab0e5b9-d87a-457e-ae58-9f4bb22e8c3d', }
        bdms = [{'id': 18, 'device_name': '/dev/vda'}]
        qos_ref = {'id': 18,
                   'total_bps': 0,
                   'total_iops': 0,
                   'read_bps': 10000,
                   'write_bps': 10000,
                   'block_device_mapping_id': 18,
                   'read_iops': 50,
                   'write_iops': 50,
                   'deleted': 0, }
        with contextlib.nested(
                mock.patch.object(self.controller.compute_api,
                                  'get', return_value=instance),
                mock.patch.object(block_device_obj.BlockDeviceMappingList,
                                  'get_by_instance_uuid',
                                  return_value=bdms),
                mock.patch.object(db,
                        'block_device_qos_get_by_block_device_mapping_id',
                                  return_value=qos_ref)):
            expected = {"qos_block_devices": [{'id': 18,
                                               'total_bps': 0,
                                               'total_iops': 0,
                                               'read_bps': 10000,
                                               'write_bps': 10000,
                                               'block_device_mapping_id': 18,
                                               'read_iops': 50,
                                               'write_iops': 50,
                                               'device_name': '/dev/vda'},
                                              ], }
            req = self._make_index_req(use_admin_context=True)
            self.assertEqual(expected,
                             self.controller.index(req, instance['uuid']))

    def test_get_invalid_server_id(self):
        req = fakes.HTTPRequest.blank(
            '/v2/fake/servers/8ab0e5b9/os-qos-block-devices')

        self.assertRaises(exc.HTTPBadRequest,
                          self.controller.index, req, 123)

    def test_get_instance_not_found(self):
        with mock.patch.object(
                self.controller.compute_api, 'get',
                side_effect=exception.InstanceNotFound(
                    instance_id='8ab0e5b9-d87a-457e-ae58-9f4bb22e8c3d')):
            self.assertRaises(exc.HTTPNotFound,
                              self.controller.index,
                              self._make_index_req(),
                              '8ab0e5b9-d87a-457e-ae58-9f4bb22e8c3d')

    def test_get_empty_bdms(self):
        instance = {'uuid': '8ab0e5b9-d87a-457e-ae58-9f4bb22e8c3d', }
        bdms = []
        with contextlib.nested(
                mock.patch.object(self.controller.compute_api,
                                  'get', return_value=instance),
                mock.patch.object(block_device_obj.BlockDeviceMappingList,
                                  'get_by_instance_uuid',
                                  return_value=bdms)):
            expected = {"qos_block_devices": [], }
            self.assertEqual(expected,
                             self.controller.index(self._make_index_req(),
                                                   instance['uuid']))

    def test_get_qos_notfound(self):
        instance = {'uuid': '8ab0e5b9-d87a-457e-ae58-9f4bb22e8c3d', }
        bdms = [{'id': 18, }]
        with contextlib.nested(
                mock.patch.object(self.controller.compute_api,
                                  'get', return_value=instance),
                mock.patch.object(block_device_obj.BlockDeviceMappingList,
                                  'get_by_instance_uuid',
                                  return_value=bdms),
                mock.patch.object(db,
                        'block_device_qos_get_by_block_device_mapping_id',
                        side_effect=exception.BlockDeviceQoSNotFoundForBDM(
                            bdm_id=18))):
            expected = {"qos_block_devices": [], }
            req = self._make_index_req(use_admin_context=True)
            self.assertEqual(expected,
                             self.controller.index(req, instance['uuid']))

    def _make_update_req(self, bdm_id):
        return fakes.HTTPRequest.blank(
            "/v2/fake/servers/8ab0e5b9-d87a-457e-ae58-9f4bb22e8c3d"
            "/os-qos-block-devices/%s" % bdm_id,
            use_admin_context=True)

    def test_put_works(self):
        instance = {'uuid': '8ab0e5b9-d87a-457e-ae58-9f4bb22e8c3d', }
        qos_ref = {'id': 28,
                   'total_bps': 0,
                   'total_iops': 0,
                   'read_bps': 10000,
                   'write_bps': 10000,
                   'block_device_mapping_id': 18,
                   'read_iops': 50,
                   'write_iops': 50,
                   'deleted': 0, }
        with contextlib.nested(
                mock.patch.object(self.controller.compute_api,
                                  'get', return_value=instance),
                mock.patch.object(db,
                                  'block_device_mapping_get_all_by_instance',
                                  return_value=[{'id': 18,
                                            'device_name': '/dev/vda'}, ]),
                mock.patch.object(db,
                            'block_device_qos_get_by_block_device_mapping_id',
                                return_value=qos_ref),
                mock.patch.object(self.controller.compute_api,
                                  'update_block_device_qos')
        ) as (_, _, _, update_blk_dev_qos):
            body = {'qos_block_device': {'total_bps': 0,
                                         'total_iops': 0,
                                         'read_bps': 2000000,
                                         'write_bps': 2000000,
                                         'read_iops': 100,
                                         'write_iops': 1000, }, }
            result = self.controller.update(
                self._make_update_req(18), 18,
                '8ab0e5b9-d87a-457e-ae58-9f4bb22e8c3d', body)
            update_blk_dev_qos.assert_called_once_with(
                mock.ANY, instance, 18, body['qos_block_device'])
            expected = body
            expected['qos_block_device']['block_device_mapping_id'] = 18
            expected['qos_block_device']['id'] = 28
            expected['qos_block_device']['device_name'] = '/dev/vda'
            self.assertEqual(expected, result)

    def test_put_invalid_bdm_id(self):
        self.assertRaises(exc.HTTPBadRequest,
                          self.controller.update,
                          self._make_update_req('abc'), 'abc',
                          'uuid', {})

    def test_put_invalid_intance_id(self):
        self.assertRaises(exc.HTTPBadRequest,
                          self.controller.update,
                          self._make_update_req(19), 19,
                          'ddd', {})

    def test_put_instance_not_found(self):
        with mock.patch.object(
                self.controller.compute_api, 'get',
                side_effect=exception.InstanceNotFound(
                    instance_id='8ab0e5b9-d87a-457e-ae58-9f4bb22e8c3d')):
            self.assertRaises(exc.HTTPNotFound,
                              self.controller.update,
                              self._make_update_req(19), 19,
                              '8ab0e5b9-d87a-457e-ae58-9f4bb22e8c3d', {})

    def test_put_qos_block_device_not_in_body(self):
        instance = {'uuid': '8ab0e5b9-d87a-457e-ae58-9f4bb22e8c3d', }
        with contextlib.nested(
                mock.patch.object(self.controller.compute_api,
                                  'get', return_value=instance),
                mock.patch.object(db,
                                  'block_device_mapping_get_all_by_instance',
                                  return_value=[{'id': 199,
                                            'device_name': '/dev/vda'}, ]),
        ):
            body = {'read_bps': 100,
                    'write_bps': 10000, }
            self.assertRaises(exc.HTTPBadRequest,
                              self.controller.update,
                              self._make_update_req(199), 199,
                              '8ab0e5b9-d87a-457e-ae58-9f4bb22e8c3d',
                              body)

    def test_put_non_integer_values_in_body(self):
        instance = {'uuid': '8ab0e5b9-d87a-457e-ae58-9f4bb22e8c3d', }
        with contextlib.nested(
                mock.patch.object(self.controller.compute_api,
                                  'get', return_value=instance),
                mock.patch.object(db,
                                  'block_device_mapping_get_all_by_instance',
                                  return_value=[{'id': 19,
                                            'device_name': '/dev/vda'}, ]),
        ):
            body = {'qos_block_device': {'write_bps': 'a', }, }
            self.assertRaises(exc.HTTPBadRequest,
                              self.controller.update,
                              self._make_update_req(19), 19,
                              '8ab0e5b9-d87a-457e-ae58-9f4bb22e8c3d',
                              body)

    def test_put_invalid_negtive_values_in_body(self):
        instance = {'uuid': '8ab0e5b9-d87a-457e-ae58-9f4bb22e8c3d', }
        with contextlib.nested(
                mock.patch.object(self.controller.compute_api,
                                  'get', return_value=instance),
                mock.patch.object(db,
                                  'block_device_mapping_get_all_by_instance',
                                  return_value=[{'id': 19,
                                                 'device_name': '/dev/vda'},
                                               ])
        ):
            body = {'qos_block_device': {'read_bps': -100,
                                         'write_bps': 10000, }, }
            self.assertRaises(exc.HTTPBadRequest,
                              self.controller.update,
                              self._make_update_req(19), 19,
                              '8ab0e5b9-d87a-457e-ae58-9f4bb22e8c3d',
                              body)

    def test_put_bdms_not_found(self):
        instance = {'uuid': '8ab0e5b9-d87a-457e-ae58-9f4bb22e8c3d', }
        with contextlib.nested(
                mock.patch.object(self.controller.compute_api,
                                  'get', return_value=instance),
                mock.patch.object(db,
                                  'block_device_mapping_get_all_by_instance',
                                  return_value=[{'id': 18,
                                             'device_name': '/dev/vda'}]),
                mock.patch.object(db,
                        'block_device_qos_get_by_block_device_mapping_id',
                        side_effect=exception.BlockDeviceQoSNotFoundForBDM(
                            bdm_id=18))
        ):
            body = {'qos_block_device': {'read_bps': 10000000,
                                         'write_bps': 10000000, }, }
            self.assertRaises(exc.HTTPNotFound,
                              self.controller.update,
                              self._make_update_req(18), 18,
                              '8ab0e5b9-d87a-457e-ae58-9f4bb22e8c3d',
                              body)

    def test_put_bdm_not_found_for_instance(self):
        instance = {'uuid': '8ab0e5b9-d87a-457e-ae58-9f4bb22e8c3d', }
        with contextlib.nested(
                mock.patch.object(self.controller.compute_api,
                                  'get', return_value=instance),
                mock.patch.object(db,
                                  'block_device_mapping_get_all_by_instance',
                                  return_value=[{'id': 30, },
                                                {'id': 33, }, ])
        ):
            self.assertRaises(exc.HTTPNotFound,
                              self.controller.update,
                              self._make_update_req(19), 19,
                              '8ab0e5b9-d87a-457e-ae58-9f4bb22e8c3d', {})
