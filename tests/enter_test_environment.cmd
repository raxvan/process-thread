
docker build -t process-thread-testenv -f ./../docker/development.dockerfile ./..

docker run ^
	--rm -it ^
	-v %~dp0/..:/process-thread ^
	-e "TERM=xterm-256color" ^
	process-thread-testenv ^
	/bin/bash


