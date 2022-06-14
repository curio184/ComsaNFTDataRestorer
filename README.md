# ComsaNFTDataRestorer

Comsa NFTのデータをSymbolチェーンからリストアするスクリプト

### 必要なライブラリをインストールする

```
$ pip install -r requirements.txt
```

### スクリプト本体を開き、必要な情報をセットする。  
* node_url : ノードのurl  
* mosaic_id : データを復元するMosaicId  
* file_path : 復元したデータの保存先  

ComsaNFTDataRestorer.py
```
node_url = "https://sym-main-07.opening-line.jp:3001"
mosaic_id = "010758BD5DF03D3A"
file_path = "./restore_data.jpg"
```

### スクリプトを実行する

```
$ python ComsaNFTDataRestorer.py
```

以上