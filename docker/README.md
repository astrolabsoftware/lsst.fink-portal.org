# Dockerfile lsst.fink-portal.org
Here is the Docker tutorial to develop lsst.fink-portal.org container on your local machines.

Make sure you have docker installed : https://docs.docker.com/get-docker/


## Develop your Docker

Fistly, you have to clone the lsst.fink-portal.org on the server in your local machine.

```bash
git clone https://github.com/astrolabsoftware/lsst.fink-portal.org
```

Enter in this new Directory.

```bash
cd lsst.fink-portal.org
```

## build your Docker image

To build a docker image, you should use `sudo docker build -f <path/to/Dockerfile> -t <image name> <path destination of your image>`

Therefore, we currently use :

```bash
sudo docker build -f docker/Dockerfile -t lsst-fink-portal .
```
Note that the . is the current directory. 
Note also that the **image size** of lsst.fink-portal.org is highly optimized (see DockerFile)

The default docker images will show all top level images, their repository and tags, and their size.

```bash
sudo docker images
```



## Run your docker

This is the documentation in order to run a command in a new container.

We set environment variables :
```bash
export HOST=0.0.0.0
export PORT=8000   # Replace 8000 with your desired port
```
We can now run with :

```bash
docker run -d -p ${PORT}:${PORT} -e HOST=${HOST} -e PORT=${PORT} lsst-fink-portal:latest
```

The `docker ps` command only shows running containers by default. We can notice The ID of each containers. 

```bash
sudo docker ps
```
Once the container is running, you can visit the portal in your browser at: http://localhost:8000 



If you have a problem during the running command, think to remove the `.bash_history` file.

```bash
ls -ltha
```
```bash
sudo rm .bash_history
```

Enter `exit` to get out of the container.

To stop and remove your container, type `sudo docker rm -f <id_of_container>`.



### Additionnal Supports

https://docs.docker.com/engine/reference/commandline/build/ 

https://docs.docker.com/engine/reference/commandline/run/

https://docs.docker.com/engine/reference/commandline/images/