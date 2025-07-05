#FROM nikolaik/python-nodejs:python3.12-nodejs22	
#FROM nikolaik/python-nodejs:python3.12-nodejs18
FROM nikolaik/python-nodejs:python3.10-nodejs18	

RUN apt-get update \
    && apt-get install -y git aria2 curl preload git ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY . /app/
WORKDIR /app/
RUN pip3 install --no-cache-dir -U -r requirements.txt
RUN rm -f *.session 
RUN rm -rf __p*

CMD bash start
