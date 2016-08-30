
.. include:: aliases.rst

.. _ha_overview:

===========
HA Overview
===========
Some applications require Congress to be highly available. Some
applications require a Congress Policy Engine (PE) to handle a high volume of
queries. This guide describes Congress support for High Availability (HA)
High Throughput (HT) deployment.

Please see the `OpenStack High Availability Guide`__ for details on how to
install and configure OpenStack for High Availability.

__ http://docs.openstack.org/ha-guide/index.html

HA Types
========

Warm Standby
~~~~~~~~~~~~
Warm Standby is when a software component is installed and available on the
secondary node. The secondary node is up and running. In the case of a
failure on the primary node, the software component is started on the
secondary node. This process is usually automated using a cluster manager.
Data is regularly mirrored to the secondary system using disk based replication
or shared disk. This generally provides a recovery time of a few minutes.

Active-Active (Load-Balanced)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
In this method, both the primary and secondary systems are active and
processing requests in parallel. Data replication happens through software
capabilities and would be bi-directional. This generally provides a recovery
time that is instantaneous.


Congress HAHT
=============
Congress provides Active-Active for the Policy Engine and Warm Standby for
the Datasource Drivers.

Run N instances of the Congress Policy Engine in active-active
configuration, so both the primary and secondary systems are active
and processing requests in parallel.

One Datasource Driver (DSD) per physical datasource, publishing data on
oslo-messaging to all policy engines.

.. code-block:: text

  +-------------------------------------+      +--------------+
  |       Load Balancer (eg. HAProxy)   | <----+ Push client  |
  +----+-------------+-------------+----+      +--------------+
       |             |             |
  PE   |        PE   |        PE   |        all+DSDs node
  +---------+   +---------+   +---------+   +-----------------+
  | +-----+ |   | +-----+ |   | +-----+ |   | +-----+ +-----+ |
  | | API | |   | | API | |   | | API | |   | | DSD | | DSD | |
  | +-----+ |   | +-----+ |   | +-----+ |   | +-----+ +-----+ |
  | +-----+ |   | +-----+ |   | +-----+ |   | +-----+ +-----+ |
  | | PE  | |   | | PE  | |   | | PE  | |   | | DSD | | DSD | |
  | +-----+ |   | +-----+ |   | +-----+ |   | +-----+ +-----+ |
  +---------+   +---------+   +---------+   +--------+--------+
       |             |             |                 |
       |             |             |                 |
       +--+----------+-------------+--------+--------+
          |                                 |
          |                                 |
  +-------+----+   +------------------------+-----------------+
  |  Oslo Msg  |   | DBs (policy, config, push data, exec log)|
  +------------+   +------------------------------------------+


- Downtime: < 1s for queries, ~2s for reactive enforcement
- Deployment considerations:

  - Cluster manager (eg. Pacemaker + Corosync) can be used to manage warm
    standby
  - Does not require global leader election
- Performance considerations:

  - Multi-process, multi-node query throughput
  - No redundant data-pulling load on datasources
  - DSDs node separate from PE, allowing high load DSDs to operate more
    smoothly and avoid affecting PE performance.
  - PE nodes are symmetric in configuration, making it easy to load balance
    evenly.

Details
~~~~~~~

- Datasource Drivers (DSDs):

  - One datasource driver per physical datasource
  - All DSDs run in a single DSE node (process)
  - Push DSDs: optionally persist data in push data DB, so a new snapshot
    can be obtained whenever needed
  - Warm Standby:

    - Only one set of DSDs running at a given time; backup instances ready
      to launch
    - For pull DSDs, warm standby is most appropriate because warm startup
      time is low (seconds) relative to frequency of data pulls
    - For push DSDs, warm standby is generally sufficient except for use cases
      that demand sub-second latency even during a failover
- Policy Engine (PE):

  - Replicate policy engine in active-active configuration.
  - Policy synchronized across PE instances via Policy DB
  - Every instance subscribes to the same data on oslo-messaging
  - Reactive Enforcement:
    All PE instances initiate reactive policy actions, but each DSD locally
    selects a leader to listen to. The DSD ignores execution requests
    initiated by all other PE instances.

    - Every PE instance computes the required reactive enforcement actions and
      initiates the corresponding execution requests over oslo-messaging
    - Each DSD locally picks a PE instance as leader (say the first instance
      the DSD hears from in the asymmetric node deployment, or the PE
      instance on the same node as the DSD in a symmetric node deployment) and
      executes only requests from that PE
    - If heartbeat contact is lost with the leader, the DSD selects a new
      leader
    - Each PE instance is unaware of whether it is a leader
  - Node Configurations:

    - Congress supports the Two Node-Types (API+PE nodes, all-DSDs) node
      configuration because it gives reasonable support for high-load DSDs
      while keeping the deployment complexities low.
  - Local Leader for Action Execution:

    - Local Leader: every PE instance sends action-execution requests, but
      each receiving DSD locally picks a "leader" to listen to
    - Because there is a single active DSD for a given data source,
      it is a natural spot to locally choose a "leader" among the PE instances
      sending reactive enforcement action execution requests. Congress
      supports the local leader style because it avoids the deployment
      complexities associated with global leader election. Furthermore,
      because all PE instances perform reactive enforcement and send action
      execution requests, the redundancy opens up the possibility for zero
      disruption to reactive enforcement when a PE instance fails.
- API:

  - Each node has an active API service
  - Each API service routes requests for the PE to its associated intranode PE
  - Requests for any other service (eg. get data source status) are routed to
    the Datasource and/or Policy Engine, which will be fielded by some active
    instance of the service on some node
- Load balancer:

  - Layer 7 load balancer (e.g. HAProxy) distributes incoming API calls among
    the nodes (each running an API service).
  - load balancer optionally configured to use sticky session to pin each API
    caller to a particular node. This configuration avoids the experience of
    going back in time.
- External components (load balancer, DBs, and oslo messaging bus) can be made
  highly available using standard solutions (e.g. clustered LB, Galera MySQL
  cluster, HA rabbitMQ)


Performance Impact
==================
- In single node deployment, there is generally no performance impact.
- Increased latency due to network communication required by multi-node
  deployment
- Increased reactive enforcement latency if action executions are persistently
  logged to facilitate smoother failover
- PE replication can achieve greater query throughput

End User Impact
===============
Different PE instances may be out-of-sync in their data and policies (eventual
consistency). The issue is generally made transparent to the end  user by
making each user sticky to a particular PE instance. But if a PE instance
goes down, the end user reaches a different instance and may experience
out-of-sync artifacts.

Installation
============
Please see :ref:`HA Deployment <ha_deployment>` for details.