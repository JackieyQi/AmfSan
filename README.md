# AmfSan


###
For clear architecture and long iteration,
Please strictly follow the order of import to business. It's forbidden for back references or skip refereces.


## Initialize mysql database
----------
    mysql> CREATE DATABASE amf DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
    mysql> CREATE USER 'myuser'@'localhost' IDENTIFIED BY 'mypass';
    mysql> CREATE USER 'myuser'@'%' IDENTIFIED BY 'mypass';
    mysql> GRANT ALL ON amf.* TO 'myuser'@'localhost';
    mysql> GRANT ALL ON amf.* TO 'myuser'@'%';
    mysql> flush privileges;
----------


## Initialize rabbitmq
----------
    $ rabbitmqctl add_user username password
    $ rabbitmqctl authenticate_user username password
----------
