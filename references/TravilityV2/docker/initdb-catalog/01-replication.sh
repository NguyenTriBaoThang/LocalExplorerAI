#!/bin/sh
# pg_hba mặc định của image chỉ mở "host all all all": dòng đó không gồm kết nối replication từ pg-catalog-replica.
echo "host replication travility all scram-sha-256" >> "$PGDATA/pg_hba.conf"
