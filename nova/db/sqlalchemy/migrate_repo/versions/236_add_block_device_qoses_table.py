# Copyright 2014 letv.com
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

from sqlalchemy import Column, DateTime, ForeignKey, Index, \
    Integer, MetaData, select, Table, UniqueConstraint

from nova.db.sqlalchemy import api
from nova.db.sqlalchemy.models import BlockDeviceMapping
from nova.db.sqlalchemy import utils
from nova.openstack.common import excutils
from nova.openstack.common.gettextutils import _
from nova.openstack.common import log as logging
from nova.openstack.common import timeutils


LOG = logging.getLogger(__name__)


def upgrade(migrate_engine):
    meta = MetaData()
    meta.bind = migrate_engine

    uc_name = 'uniq_block_device_qoses0block_device_mapping_id'
    block_device_qoses = Table('block_device_qoses', meta,
                    Column('created_at', DateTime(timezone=False)),
                    Column('updated_at', DateTime(timezone=False)),
                    Column('deleted_at', DateTime(timezone=False)),
                    Column('deleted', Integer, default=0, nullable=False),
                    Column('id', Integer, primary_key=True, nullable=False),
                    Column('read_bps', Integer, default=0),
                    Column('write_bps', Integer, default=0),
                    Column('total_bps', Integer, default=0),
                    Column('read_iops', Integer, default=0),
                    Column('write_iops', Integer, default=0),
                    Column('total_iops', Integer, default=0),
                    Column('block_device_mapping_id', Integer,
                           ForeignKey(BlockDeviceMapping.id),
                           nullable=False),
                    UniqueConstraint('block_device_mapping_id', name=uc_name),
                    Index('ix_block_device_qoses_block_device_mapping_id',
                          'block_device_mapping_id'),
                    mysql_engine='InnoDB',
                    mysql_charset='utf8')
    try:
        block_device_qoses.create()
        utils.create_shadow_table(migrate_engine, table=block_device_qoses)
    except Exception:
        with excutils.save_and_reraise_exception():
            LOG.exception(_("Exception while creating table"
                            " 'block_device_qoses'."))

    now = timeutils.utcnow()
    blk_map_table = Table('block_device_mapping', meta, autoload=True)
    for blk_map_id, in select(columns=[blk_map_table.c.id],
                              whereclause=(blk_map_table.c.deleted == 0)
                          ).execute().fetchall():
        block_device_qoses.insert().values(created_at=now, updated_at=now,
                    deleted=0, block_device_mapping_id=blk_map_id).execute()


def downgrade(migrate_engine):
    meta = MetaData()
    meta.bind = migrate_engine

    block_device_qoses = Table('block_device_qoses', meta, autoload=True)
    shadow_block_device_qoses = Table(api._SHADOW_TABLE_PREFIX +
                                      'block_device_qoses',
                                      meta, autoload=True)
    try:
        block_device_qoses.drop()
        shadow_block_device_qoses.drop()
    except Exception:
        with excutils.save_and_reraise_exception():
            LOG.exception(_("Exception while dropping table"
                            " 'block_device_qoses'."))
