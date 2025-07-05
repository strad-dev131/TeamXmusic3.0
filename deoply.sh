docker container rm TeamXop -f > /dev/null
sleep 2
echo "Starting and Deploying Bot as TeamXop"
docker run -d --restart=always --name TeamXop TeamXop
