### 程序运行：

### 1.安装wine

```shell
sudo apt-get install wine
```

### 2.运行rtmp-rtsp.exe文件

```shell
wine rtmp-rtsp.exe
```

### 3.修改配置文件

```shell
vim ./configs/config.yaml
```

### 4.运行主程序app.py文件

```shell
python app.py
```

## 各部分功能：

configs：存放配置文件

logs：存放日志文件

tools：存放主程序各功能模块文件

utils：存放工具函数和辅助函数

models：存放模型相关文件

weights：存放模型权重文件