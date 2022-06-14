import base64
import codecs
import hashlib
import json
from binascii import hexlify, unhexlify
from time import sleep
from typing import Dict, List, Tuple

import requests
import sha3


class KeyGenerator:

    @staticmethod
    def generate_uint64_key(input: str) -> int:
        # 下記コマンドと互換 (と思いきや先頭桁のみ稀に違う...末尾15桁の比較で回避)
        # $ symbol-cli converter stringToKey -v header
        # AD6D8491D21180E5D
        hasher = sha3.sha3_256()
        hasher.update(input.encode("utf-8"))
        digest = hasher.digest()
        result = int.from_bytes(digest[0:8], "little")
        return result


class IdConverter:

    @staticmethod
    def decimal_int_to_hex_str(decimal_int: int) -> str:
        return "{:0>16}".format(hex(decimal_int)[2:].upper())

    @staticmethod
    def hex_str_to_decimal_int(hex_str: str) -> int:
        return int(hex_str, 16)


class JsonFile:

    @staticmethod
    def save(file_path: str, data: dict):
        """
        JSONを保存する
        """
        with codecs.open(file_path, "w", "utf8") as f:
            json.dump(data, f, ensure_ascii=False)

    @staticmethod
    def load(file_path: str) -> dict:
        """
        JSONを読み込む
        """
        data = None
        with codecs.open(file_path, "r", "utf8") as f:
            data = json.load(f)
        return data


class File:

    @staticmethod
    def load_as_base64(file_path: str) -> str:
        """
        ファイルをBase64でエンコードし文字列として読み込む
        """
        with open(file_path, "rb") as f:
            file_binary = base64.b64encode(f.read())
        return file_binary.decode('utf-8')

    @staticmethod
    def save_file_base64(file_path: str, file_base64: str):
        """
        Base64でエンコードされたファイルを保存する
        """
        with open(file_path, "wb") as f:
            f.write(base64.b64decode(file_base64))

    @staticmethod
    def get_file_hash(file_path: str) -> str:
        """
        ファイルのハッシュ(sha256)を取得する
        """
        with open(file_path, "rb") as f:
            hash_sha256 = hashlib.sha256(f.read()).hexdigest()
        return hash_sha256

    @staticmethod
    def get_file_base64_hash(file_base64: str) -> str:
        """
        Base64でエンコードされたファイルのハッシュ(sha256)を取得する
        """
        file_binary = base64.b64decode(file_base64)
        return hashlib.sha256(file_binary).hexdigest()


class CatapultRESTAPI:

    def __init__(self, node_url: str) -> None:
        self._node_url = node_url

    def get_epoch_adjustment(self) -> int:
        """
        epochAdjustmentを取得する
        """
        url = self._node_url + "/network/properties"
        response = requests.get(url)
        if response.status_code != 200:
            raise Exception("status code is {}".format(response.status_code))
        contents = json.loads(response.text)
        epoch_adjustment = int(contents["network"]["epochAdjustment"].replace("s", ""))
        return epoch_adjustment

    def get_currency_mosaic_id(self) -> int:
        """
        currencyMosaicIdを取得する
        """
        url = self._node_url + "/network/properties"
        response = requests.get(url)
        if response.status_code != 200:
            raise Exception("status code is {}".format(response.status_code))
        contents = json.loads(response.text)
        currency_mosaic_id = int(contents["chain"]["currencyMosaicId"].replace("'", ""), 16)
        return currency_mosaic_id

    def get_mosaic_info(self, mosaic_id: str) -> Dict:
        """
        Get mosaic information
        """
        url = self._node_url + "/mosaics/" + mosaic_id
        response = requests.get(url)
        if response.status_code != 200:
            raise Exception("status code is {}".format(response.status_code))
        return json.loads(response.text)

    def get_mosaic_metadata(self, mosaic_id: str) -> Dict:
        """
        Get mosaic metadata
        """
        url = self._node_url + "/metadata"
        params = {
            "targetId": mosaic_id,
            "metadataType": 1
        }
        response = requests.get(url, params=params)
        if response.status_code != 200:
            raise Exception("status code is {}".format(response.status_code))
        return json.loads(response.text)

    def get_confirmed_transaction_info(self, transaction_id: str) -> Dict:
        """
        Get confirmed transaction information
        """
        url = self._node_url + "/transactions/confirmed/" + transaction_id
        response = requests.get(url)
        if response.status_code != 200:
            raise Exception("status code is {}".format(response.status_code))
        return json.loads(response.text)


class ComsaNFTDataEncoder:

    @staticmethod
    def decode_messages_to_file_base64(messages: List[str]) -> str:
        """
        メッセージをファイルにデコードする
        """

        # メッセージをメタデータ行とデータ行に分解する
        metadata_records: List[str] = []
        data_records: List[Tuple[int, str]] = []
        for message in messages:
            if message[0:5].isnumeric() and message[5:6] == "#":
                data_records.append((int(message[0:5]), message[6:]))
            else:
                metadata_records.append(json.loads(message))

        # メタデータ行を検証する
        file_hash = ""
        for idx, metadata_record in enumerate(metadata_records):
            if idx == 0:
                file_hash = metadata_record["hash"]
            else:
                if metadata_record["hash"] != file_hash:
                    raise Exception("File hashes do not match.")

        # データ行を検証する
        file_base64 = ""
        data_records = sorted(data_records, key=lambda x: x[0])
        for idx, data_record in enumerate(data_records):
            if data_record[0] != idx:
                raise Exception("Part of the message is missing.")
            file_base64 = file_base64 + data_record[1]

        if File.get_file_base64_hash(file_base64) != file_hash:
            raise Exception("File hashes do not match.")

        return file_base64


class ComsaNFTDataRestorer:

    def __init__(self, node_url: str):

        # ネットワーク情報
        self._node_url = node_url

    def restore_nft_data(self, mosaic_id: str, file_path: str):
        """
        NFTデータを復元する

        Parameters
        ----------
        mosaic_id : str
            モザイクID
        file_path : str
            ファイルの保存先
        """

        catapult_api = CatapultRESTAPI(self._node_url)

        # モザイクのメタデータを取得する
        print("get_mosaic_metadata.")
        mosaic_metadata = catapult_api.get_mosaic_metadata(mosaic_id)
        JsonFile.save("mosaic_metadata.json", mosaic_metadata)

        # モザイクのメタデータからNFT概要と参照データを取得する
        metadata_nft, tx_hashes = self._parse_mosaic_metadata(mosaic_metadata)

        messages: List[str] = []
        for idx, tx_hash in enumerate(tx_hashes):

            # トランザクション情報を取得する
            print("get_confirmed_transaction_info. {}/{}".format(idx + 1, len(tx_hashes)))
            aggregate_tx_info = catapult_api.get_confirmed_transaction_info(tx_hash)
            JsonFile.save("transaction_info_{}.json".format(idx), mosaic_metadata)

            # トランザクション情報からメッセージを取得する
            for tx_info in aggregate_tx_info["transaction"]["transactions"]:
                message = tx_info["transaction"]["message"]
                message = unhexlify(message.encode("utf-8"))[1:].decode("utf-8")
                messages.append(message)

            sleep(3)

        # メッセージをファイルにデコードする
        file_base64 = ComsaNFTDataEncoder.decode_messages_to_file_base64(messages)

        # Base64でエンコードされたファイルを保存する
        File.save_file_base64(file_path, file_base64)

    def _parse_mosaic_metadata(self, mosaic_metadata: Dict) -> Tuple[Dict, List[str]]:
        """
        モザイクのメタデータからNFT情報とハッシュリストを取得する

        Parameters
        ----------
        mosaic_metadata : Dict
            モザイクのメタデータ

        Returns
        -------
        Tuple[Dict, List[str]]
            (NFTに関する情報, アグリゲートトランザクションのハッシュリスト)
        """

        # NOTE:
        # generate_uint64_keyの生成

        # NFTに関する情報
        metadata_key_nft = IdConverter.decimal_int_to_hex_str(KeyGenerator.generate_uint64_key("nft"))
        # 総アグリゲートトランザクション数(Original Input不明のため定数)
        key_data_length = "FE58A23DBB642C67"

        # メタデータ(NFTに関する情報)
        key_values = list(filter(
            lambda x: x["metadataEntry"]["scopedMetadataKey"][-15:] == metadata_key_nft[-15:],
            mosaic_metadata["data"]
        ))
        if len(key_values) != 1:
            raise Exception("Not Found Metadata Key")
        metadata_value = key_values[0]["metadataEntry"]["value"]
        metadata_nft = json.loads(unhexlify(metadata_value.encode("utf-8")).decode("utf-8"))

        # メタデータ(総アグリゲートトランザクション数)
        key_values = list(filter(
            lambda x: x["metadataEntry"]["scopedMetadataKey"][-15:] == key_data_length[-15:],
            mosaic_metadata["data"]
        ))
        if len(key_values) != 1:
            raise Exception("Not Found Metadata Key")
        metadata_value = key_values[0]["metadataEntry"]["value"]
        metadata_data_length = int(unhexlify(metadata_value.encode("utf-8")).decode("utf-8"))

        # メタデータ(アグリゲートトランザクションのハッシュリスト)
        data_index = 1
        tx_hashes: List[str] = []
        while True:
            key_data = IdConverter.decimal_int_to_hex_str(KeyGenerator.generate_uint64_key("data" + str(data_index)))
            key_values = list(filter(
                lambda x: x["metadataEntry"]["scopedMetadataKey"][-15:] == key_data[-15:],
                mosaic_metadata["data"]
            ))
            if len(key_values) != 1:
                break
            metadata_value = key_values[0]["metadataEntry"]["value"]
            tx_hashes.extend(json.loads(unhexlify(metadata_value.encode("utf-8")).decode("utf-8")))
            data_index = data_index + 1

        if len(tx_hashes) != metadata_data_length:
            raise Exception("Transaction counts do not match.")

        return (metadata_nft, tx_hashes)


if __name__ == "__main__":

    node_url = "https://***.***.***:3001"
    mosaic_id = "010758BD5DF03D3A"
    file_path = "./restore_data.jpg"

    restorer = ComsaNFTDataRestorer(node_url)
    restorer.restore_nft_data(mosaic_id, file_path)
