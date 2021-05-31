# Network-Measure-qqbot
一个提供网络测量工具的QQ BOT
使用go-cqhttp api

# 依赖
python >= 3.8

1. python packages
```
pip3 install aiohttp
pip3 install selenium
```

2. selenium firefox driver
见: https://www.selenium.dev/documentation/en/webdriver/driver_requirements/

3. firefox browser

4. network-measure api
https://github.com/tongyuantongyu/network-measure
下载 release binary
编辑 config.toml (见: https://github.com/tongyuantongyu/network-measure/exec/http/config.example.toml)
配置ip地址 端口号 和密码，并将信息填入本机器人的config.py
在需要的地方运行此api(可以多处运行多个api)

5. go-cqhttp
https://github.com/Mrs4s/go-cqhttp
使用go-cqhttp反向websocket api
配置文件例子见config.yml

# 机器人命令
![image](https://github.com/LDLDL/Network-Measure-qqbot/mdpic/command.jpg)
![image](https://github.com/LDLDL/Network-Measure-qqbot/mdpic/mtr.jpg)
![image](https://github.com/LDLDL/Network-Measure-qqbot/mdpic/speed.jpg)
