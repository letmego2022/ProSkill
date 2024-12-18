from datetime import datetime
import requests
import os


def extract_text_from_file(file_path):
    """
    使用Tika Server提取文件内容并优化文本格式

    Args:
        file_path: 文件路径

    Returns:
        str: 提取并优化后的文本内容
    """
    try:
        # Tika Server的默认地址
        tika_server_url = 'http://localhost:9998/tika'

        # 检查文件是否存在
        if not os.path.exists(file_path):
            print(f"文件未找到: {file_path}")
            return None

        # 打开并读取文件
        with open(file_path, 'rb') as file:
            # 发送POST请求到Tika Server，自动识别文件类型
            headers = {
                'Accept': 'text/plain'  # 指定返回纯文本格式
            }
            response = requests.put(tika_server_url, data=file, headers=headers)

            # 检查响应状态
            if response.status_code == 200:
                # 设置响应的字符编码为UTF-8（如果是中文，可以尝试其他编码，如GBK）
                response.encoding = 'utf-8'  # 可以尝试'gbk' 或 'utf-8-sig'，根据需要调整
                # 获取原始文本
                text = response.text
                # 处理文本
                # 1. 去除多余的空行（保留单个空行）
                text = '\n'.join(line for line in text.splitlines() if line.strip())
                # 2. 合并不以句号、问号、感叹号结尾的行
                lines = text.splitlines()
                merged_lines = []
                temp_line = ''
                for line in lines:
                    line = line.strip()
                    if not line:
                        if temp_line:
                            merged_lines.append(temp_line)
                            temp_line = ''
                        merged_lines.append('')  # 空行
                    elif line[-1] in '.。!！?？':
                        # 如果该行以句号、问号、感叹号结尾，合并并添加到列表
                        temp_line = (temp_line + ' ' + line).strip() if temp_line else line
                        merged_lines.append(temp_line)
                        temp_line = ''
                    else:
                        # 否则，将该行合并到临时行
                        temp_line = (temp_line + ' ' + line).strip() if temp_line else line

                # 如果临时行还有内容，添加到结果中
                if temp_line:
                    merged_lines.append(temp_line)

                # 3. 合并结果
                processed_text = '\n'.join(merged_lines)

                return processed_text
            else:
                print(f"提取失败, 状态码: {response.status_code}, 错误信息: {response.text}")
                return None
    except requests.exceptions.ConnectionError:
        print("无法连接到Tika Server，请确保服务已启动")
        return None
    except Exception as e:
        print(f"发生错误: {str(e)}")
        return None

def convert_date_range_to_string(date_range):
    """
    将日期范围字符串（如"10月1号到12月31号"）转换为指定年份的日期字符串（如"2024-10-01"到"2024-12-31"）。

    参数:
    date_range (str): 日期范围字符串，格式为"开始月份日期号到结束月份日期号"。
    year (str): 年份，格式为"YYYY"。

    返回:
    tuple: 包含开始日期和结束日期的元组，格式为("YYYY-MM-DD", "YYYY-MM-DD")。
    """
    # 分割日期范围
    base_start, base_end = date_range.split("到")
    return base_start, base_end



# 定义日期范围比较函数
def compare_date_range(base_start, base_end, start, end):
    # 将日期字符串转换为datetime对象
    base_d_start = datetime.strptime(base_start, "%Y-%m-%d")
    base_d_end = datetime.strptime(base_end, "%Y-%m-%d")
    d_start = datetime.strptime(start, "%Y-%m-%d")
    d_end = datetime.strptime(end, "%Y-%m-%d")

    # 检查是否完全包含
    if d_start >= base_d_start and d_end <= base_d_end:
        return f"-完全冲突，不符合：项目时间 {start} 到 {end} 完全包含在当前排期中"
    # 检查是否有部分重叠
    elif d_start <= base_d_end and d_end >= base_d_start:
        return f"-存在冲突：项目时间 {start} 到 {end} 与当前排期存在重叠"
    # 无重叠
    else:
        return f"-无冲突：项目 {start} 到 {end} 与当前排期没有任何重叠"


def is_date_out_of_range(start_date_str, end_date_str):
    # 获取当前日期
    current_date = datetime.now()

    # 将字符串转换为日期对象
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")

    # 判断当前日期是否在时间段内
    return not (start_date <= current_date <= end_date)