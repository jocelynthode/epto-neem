# Run locally
To run locally just call `cluster/run_benchmarks.py` with the `--local` option in the application folder you want to run. This will create the docker container and the service running it.

**Take care of adjusting values in the scripts file to your own computer!**

# Cluster Setup Instructions

These instructions explain how to setup a remote cluster with Docker 1.12 to run EpTO tests. Debian is used on our virtual machines managed by OpenNebula. These instructions were created using the model offered by Sébastien Vaucher[[1]](https://github.com/sebyx31/ErasureBench/blob/master/projects/erasure-tester/swarm_instructions.md)

##  Setup the image

1. Install Debian stable
2. Install the kernel from the backports
3. Install Docker >= 1.12
4. Create /etc/systemd/system/docker.service.d/docker.conf with the following content:

    ```
    [Service]
    ExecStart=
    ExecStart=/usr/bin/docker daemon -H fd:// -H tcp://0.0.0.0:2375 -H unix:///var/run/docker.sock
    TasksMax=infinity
    ```

    **Warning !** When running on an environment where IPs in the 172.16.0.0/12 subnet might be in use, it is wise to tell Docker to use another RFC 1918 subnet. Example to add to ExecStart (note that it is a machine IP, not the network IP):
    
    ```
    --bip=10.93.0.1/24
    ```
    
5. Install opennebula-context
6. Delete /etc/docker/key.json (Regenerated on startup)

## Configure the System on OpenNebula
Copy this image on OpenNebula.

### All machines
1. Change the hostname in /etc/{hosts,hostname} to be different on each machine (and add the master hostname to every machine)
  ```
  hostnamectl set-hostname mymachine
  systemctl restart docker
  ```


2. Mount the volatile disk on /var/lib/docker (through /etc/fstab)

### Master
1. Generate a private ssh key 

  ```
  ssh-keygen
  ```
2. Copy it to every worker

  ```
  for i X Y Z; do
    ssh-copy-id debian@{IP}.${i}
  done 
  ```

3. Create the X.509 certificate for the registry 


  ```
 mkdir -p certs && openssl req \
 -newkey rsa:4096 -nodes -sha256 -keyout certs/domain.key \
 -x509 -days 365 -out certs/domain.crt
  ```
  
4. Copy the created domain.crt as /etc/docker/certs.d/swarm-m:5000/ca.crt on ALL machines 

  
5. Start the Docker repository
 
    ```
    docker run -d -p 5000:5000 --restart=always --name registry \
      -v `pwd`/certs:/certs \
      -e REGISTRY_HTTP_TLS_CERTIFICATE=/certs/domain.crt \
      -e REGISTRY_HTTP_TLS_KEY=/certs/domain.key \
      registry:2
    ```

## Deploy the application

### Automated way (with manual data collection from the hosts)
This way assumes you have a SSH key-pair to connect to your master.
**Take care of adjusting values in the scripts file to your own computer!**
 ```
 ./setup_cluster.sh
 ```
 
## Run the benchmarks (on the master node)
 **Take care of adjusting values in the scripts file to your own computer!**
* start ~/{epto,jgroups}/run_benchmarks.py
* Wait for the script to complete

# Verify Results
To verify the validity of the collected results multiple scripts are provided in the folder results.
* You can verify the pss health
* You can verify the order of the events sent, discarding holes with `check_order.py`. This script will also log all events that were logged as sent, but were never sent in practice due to churn. This file is to be used with `{epto,jgroups}-tester.py`
* You can verify that EpTO and JGroups do indeed deliver the required number of events and generate the different csv to use for figures with `{epto,jgroups}-tester.py`
