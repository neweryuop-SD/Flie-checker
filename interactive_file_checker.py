#!/usr/bin/env python3
"""
文件检测工具 - 点击运行后弹出控制台交互界面
"""

import os
import sys
import time
import json
import threading
from queue import Queue
from datetime import datetime
import ctypes

# 设置控制台窗口标题
ctypes.windll.kernel32.SetConsoleTitleW("文件检测工具 v1.0")

# 清屏并显示欢迎信息
os.system('cls' if os.name == 'nt' else 'clear')


def print_header():
    """打印标题"""
    print("\n" + "=" * 60)
    print(" " * 15 + "📁 文件检测工具 v1.0 📁")
    print("=" * 60)
    print("功能：批量检测文件是否可读、完整可用")
    print("=" * 60)


def print_menu():
    """打印主菜单"""
    print("\n请选择检测模式：")
    print("┌──────────────────────────────────────────┐")
    print("│ 1. 检测单个目录                         │")
    print("│ 2. 检测多个目录                         │")
    print("│ 3. 从文件列表读取（txt文件）            │")
    print("│ 4. 直接输入文件路径                     │")
    print("│ 5. 设置选项（线程数、扩展名过滤等）     │")
    print("│ 6. 退出程序                             │")
    print("└──────────────────────────────────────────┘")


class FileChecker:
    """文件检测器核心类"""

    def __init__(self, max_workers=4):
        self.max_workers = max_workers
        self.results = []
        self.total_files = 0
        self.processed = 0
        self.start_time = None
        self.lock = threading.Lock()

    def check_file(self, filepath):
        """检查单个文件"""
        result = {
            'file': filepath,
            'filename': os.path.basename(filepath),
            'exists': False,
            'readable': False,
            'size': 0,
            'error': None
        }

        try:
            if not os.path.exists(filepath):
                result['error'] = "文件不存在"
                return result

            result['exists'] = True
            size = os.path.getsize(filepath)
            result['size'] = size

            if size == 0:
                result['error'] = "空文件"
                return result

            # 尝试读取文件
            try:
                with open(filepath, 'rb') as f:
                    # 读取文件头部确认可读性
                    f.read(min(4096, size))
                result['readable'] = True
            except PermissionError:
                result['error'] = "权限不足"
            except Exception as e:
                result['error'] = f"读取失败: {str(e)[:50]}"

        except Exception as e:
            result['error'] = f"检查错误: {str(e)[:50]}"

        return result

    def worker(self, file_queue):
        """工作线程函数"""
        while True:
            try:
                filepath = file_queue.get_nowait()
            except:
                break

            # 检查文件
            result = self.check_file(filepath)

            with self.lock:
                self.results.append(result)
                self.processed += 1

                # 显示进度
                progress = self.processed / self.total_files * 100
                status = "✓" if result['readable'] else "✗"

                # 进度条显示
                bar_length = 30
                filled = int(bar_length * self.processed // self.total_files)
                bar = '█' * filled + '░' * (bar_length - filled)

                sys.stdout.write(
                    f"\r[{bar}] {self.processed}/{self.total_files} ({progress:.1f}%) {status} {result['filename'][:30]}")
                sys.stdout.flush()

            file_queue.task_done()

    def check_batch(self, file_list):
        """批量检查文件"""
        if not file_list:
            return []

        self.total_files = len(file_list)
        self.processed = 0
        self.results = []
        self.start_time = time.time()

        print(f"\n开始检查 {self.total_files} 个文件...")
        print("=" * 60)

        # 创建队列
        file_queue = Queue()
        for filepath in file_list:
            file_queue.put(filepath)

        # 创建工作线程
        threads = []
        for i in range(min(self.max_workers, self.total_files)):
            t = threading.Thread(target=self.worker, args=(file_queue,))
            t.daemon = True
            t.start()
            threads.append(t)

        # 等待所有线程完成
        for t in threads:
            t.join()

        # 换行
        print()

        return self.results


def scan_directory(directory, recursive=True, extensions=None):
    """扫描目录获取文件列表"""
    if not os.path.isdir(directory):
        print(f"错误: 目录 '{directory}' 不存在")
        return []

    file_list = []

    if recursive:
        # 递归扫描
        print(f"正在扫描目录: {directory}")
        for root, dirs, files in os.walk(directory):
            for file in files:
                full_path = os.path.join(root, file)
                if extensions:
                    ext = os.path.splitext(file)[1].lower()
                    if ext in [e.lower() for e in extensions]:
                        file_list.append(full_path)
                else:
                    file_list.append(full_path)
    else:
        # 只扫描当前目录
        print(f"正在扫描目录: {directory}")
        for item in os.listdir(directory):
            full_path = os.path.join(directory, item)
            if os.path.isfile(full_path):
                if extensions:
                    ext = os.path.splitext(item)[1].lower()
                    if ext in [e.lower() for e in extensions]:
                        file_list.append(full_path)
                else:
                    file_list.append(full_path)

    print(f"找到 {len(file_list)} 个文件")
    return file_list


def load_file_list(filename):
    """从文件加载文件列表"""
    if not os.path.exists(filename):
        print(f"错误: 文件 '{filename}' 不存在")
        return []

    file_list = []
    with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if line and not line.startswith('#'):
                if os.path.exists(line):
                    file_list.append(line)
                else:
                    print(f"警告: 第{line_num}行文件不存在: {line}")

    print(f"从 '{filename}' 加载了 {len(file_list)} 个有效文件")
    return file_list


def show_results_summary(results, total_time):
    """显示检查结果摘要"""
    if not results:
        return

    total = len(results)
    good = sum(1 for r in results if r['readable'])
    bad = total - good

    print("\n" + "=" * 60)
    print("检测结果摘要")
    print("=" * 60)
    print(f"📊 统计信息:")
    print(f"   总文件数: {total}")
    print(f"   正常文件: {good} 个 ({good / total * 100:.1f}%)")
    print(f"   问题文件: {bad} 个 ({bad / total * 100:.1f}%)")
    print(f"   检查用时: {total_time:.1f} 秒")
    print(f"   平均速度: {total / total_time:.1f} 文件/秒")
    print()

    # 显示问题文件列表
    if bad > 0:
        print("⚠️ 问题文件列表:")
        print("-" * 60)

        # 按错误类型分组
        errors = {}
        for result in results:
            if not result['readable'] and result['error']:
                error_type = result['error']
                if error_type not in errors:
                    errors[error_type] = []
                errors[error_type].append(result)

        for error_type, files in errors.items():
            print(f"\n{error_type} ({len(files)} 个):")
            for result in files[:10]:  # 每种错误最多显示10个
                print(f"  • {result['filename']} ({result['size']:,} 字节)")
            if len(files) > 10:
                print(f"  ... 还有 {len(files) - 10} 个文件")

        print(f"\n总计 {bad} 个文件需要关注")
    else:
        print("🎉 所有文件都正常！")

    print("=" * 60)


def save_results_to_file(results, total_time):
    """保存检查结果到文件"""
    if not results:
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    txt_file = f"文件检测报告_{timestamp}.txt"
    json_file = f"文件检测报告_{timestamp}.json"

    total = len(results)
    good = sum(1 for r in results if r['readable'])
    bad = total - good

    # 保存为文本文件
    with open(txt_file, 'w', encoding='utf-8') as f:
        f.write("文件检测报告\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"总文件数: {total}\n")
        f.write(f"正常文件: {good} 个\n")
        f.write(f"问题文件: {bad} 个\n")
        f.write(f"检查用时: {total_time:.1f} 秒\n\n")

        if bad > 0:
            f.write("问题文件详情:\n")
            f.write("-" * 60 + "\n")
            for result in results:
                if not result['readable']:
                    f.write(f"文件: {result['file']}\n")
                    f.write(f"错误: {result['error']}\n")
                    f.write(f"大小: {result['size']:,} 字节\n")
                    f.write("-" * 40 + "\n")

        f.write("\n报告结束\n")
        f.write("=" * 60)

    # 保存为JSON文件
    report_data = {
        'timestamp': datetime.now().isoformat(),
        'summary': {
            'total_files': total,
            'good_files': good,
            'bad_files': bad,
            'total_time': total_time
        },
        'results': results
    }

    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    return txt_file, json_file


def get_settings():
    """获取用户设置"""
    settings = {
        'threads': 4,
        'extensions': None,
        'recursive': True
    }

    print("\n" + "=" * 60)
    print("设置选项")
    print("=" * 60)

    try:
        # 设置线程数
        threads = input(f"设置线程数 (1-16, 默认{settings['threads']}): ").strip()
        if threads:
            try:
                threads = int(threads)
                if 1 <= threads <= 16:
                    settings['threads'] = threads
                else:
                    print("线程数必须在1-16之间，使用默认值")
            except:
                print("无效输入，使用默认值")

        # 设置扩展名过滤
        ext_input = input("设置扩展名过滤 (用空格分隔，如: .pdf .docx，留空检测所有): ").strip()
        if ext_input:
            settings['extensions'] = ext_input.split()

        # 设置是否递归
        recursive = input("是否递归子目录? (y/n, 默认y): ").strip().lower()
        settings['recursive'] = recursive != 'n'

        print("设置已保存！")
    except KeyboardInterrupt:
        print("\n取消设置")

    return settings


def main():
    """主函数"""
    # 初始化设置
    settings = {
        'threads': 4,
        'extensions': None,
        'recursive': True
    }

    # 创建检测器
    checker = FileChecker(max_workers=settings['threads'])

    while True:
        # 显示标题和菜单
        print_header()
        print_menu()

        try:
            choice = input("\n请输入选项 (1-6): ").strip()

            if choice == '1':
                # 检测单个目录
                directory = input("\n请输入目录路径 (直接回车选择当前目录): ").strip()
                if not directory:
                    directory = '.'

                print(f"\n即将检测目录: {directory}")
                print(
                    f"设置: 线程数={settings['threads']}, 递归={settings['recursive']}, 扩展名={settings['extensions'] or '所有'}")

                confirm = input("是否开始检测? (y/n): ").strip().lower()
                if confirm == 'y':
                    # 扫描目录获取文件列表
                    file_list = scan_directory(
                        directory,
                        settings['recursive'],
                        settings['extensions']
                    )

                    if file_list:
                        # 更新检测器线程数
                        checker.max_workers = settings['threads']

                        # 开始检测
                        results = checker.check_batch(file_list)
                        total_time = time.time() - checker.start_time

                        # 显示结果
                        show_results_summary(results, total_time)

                        # 保存结果
                        save_option = input("\n是否保存检测报告? (y/n, 默认y): ").strip().lower()
                        if save_option != 'n':
                            txt_file, json_file = save_results_to_file(results, total_time)
                            print(f"\n报告已保存:")
                            print(f"文本报告: {txt_file}")
                            print(f"JSON报告: {json_file}")

                    input("\n按回车键继续...")

            elif choice == '2':
                # 检测多个目录
                print("\n请输入目录路径 (每行一个，空行结束):")
                directories = []
                while True:
                    directory = input().strip()
                    if not directory:
                        break
                    if os.path.isdir(directory):
                        directories.append(directory)
                    else:
                        print(f"警告: 目录不存在: {directory}")

                if directories:
                    print(f"\n即将检测 {len(directories)} 个目录")
                    print(
                        f"设置: 线程数={settings['threads']}, 递归={settings['recursive']}, 扩展名={settings['extensions'] or '所有'}")

                    confirm = input("是否开始检测? (y/n): ").strip().lower()
                    if confirm == 'y':
                        all_files = []
                        for directory in directories:
                            files = scan_directory(
                                directory,
                                settings['recursive'],
                                settings['extensions']
                            )
                            all_files.extend(files)

                        if all_files:
                            checker.max_workers = settings['threads']
                            results = checker.check_batch(all_files)
                            total_time = time.time() - checker.start_time

                            show_results_summary(results, total_time)

                            save_option = input("\n是否保存检测报告? (y/n, 默认y): ").strip().lower()
                            if save_option != 'n':
                                txt_file, json_file = save_results_to_file(results, total_time)
                                print(f"\n报告已保存:")
                                print(f"文本报告: {txt_file}")
                                print(f"JSON报告: {json_file}")

                    input("\n按回车键继续...")

            elif choice == '3':
                # 从文件列表读取
                list_file = input("\n请输入文件列表路径 (txt文件): ").strip()
                if list_file and os.path.exists(list_file):
                    print(f"\n即将从文件读取文件列表: {list_file}")
                    print(f"设置: 线程数={settings['threads']}")

                    confirm = input("是否开始检测? (y/n): ").strip().lower()
                    if confirm == 'y':
                        file_list = load_file_list(list_file)

                        if file_list:
                            checker.max_workers = settings['threads']
                            results = checker.check_batch(file_list)
                            total_time = time.time() - checker.start_time

                            show_results_summary(results, total_time)

                            save_option = input("\n是否保存检测报告? (y/n, 默认y): ").strip().lower()
                            if save_option != 'n':
                                txt_file, json_file = save_results_to_file(results, total_time)
                                print(f"\n报告已保存:")
                                print(f"文本报告: {txt_file}")
                                print(f"JSON报告: {json_file}")

                    input("\n按回车键继续...")
                else:
                    print("文件不存在或未指定文件路径")
                    input("\n按回车键继续...")

            elif choice == '4':
                # 直接输入文件路径
                print("\n请输入文件路径 (每行一个，空行结束):")
                file_list = []
                while True:
                    filepath = input().strip()
                    if not filepath:
                        break
                    file_list.append(filepath)

                if file_list:
                    print(f"\n即将检测 {len(file_list)} 个文件")
                    print(f"设置: 线程数={settings['threads']}")

                    confirm = input("是否开始检测? (y/n): ").strip().lower()
                    if confirm == 'y':
                        checker.max_workers = settings['threads']
                        results = checker.check_batch(file_list)
                        total_time = time.time() - checker.start_time

                        show_results_summary(results, total_time)

                        save_option = input("\n是否保存检测报告? (y/n, 默认y): ").strip().lower()
                        if save_option != 'n':
                            txt_file, json_file = save_results_to_file(results, total_time)
                            print(f"\n报告已保存:")
                            print(f"文本报告: {txt_file}")
                            print(f"JSON报告: {json_file}")

                    input("\n按回车键继续...")
                else:
                    print("未输入任何文件路径")
                    input("\n按回车键继续...")

            elif choice == '5':
                # 设置选项
                new_settings = get_settings()
                if new_settings:
                    settings = new_settings
                    print(f"\n当前设置:")
                    print(f"  线程数: {settings['threads']}")
                    print(f"  扩展名过滤: {settings['extensions'] or '所有文件'}")
                    print(f"  递归子目录: {'是' if settings['recursive'] else '否'}")

                input("\n按回车键返回主菜单...")

            elif choice == '6':
                # 退出程序
                print("\n感谢使用文件检测工具！")
                print("程序将在3秒后退出...")
                time.sleep(3)
                break

            else:
                print("\n无效选项，请输入1-6")
                time.sleep(1)

        except KeyboardInterrupt:
            print("\n\n检测到Ctrl+C，是否退出程序? (y/n): ", end='')
            try:
                confirm = input().strip().lower()
                if confirm == 'y':
                    print("\n程序退出")
                    break
            except KeyboardInterrupt:
                print("\n程序退出")
                break
        except Exception as e:
            print(f"\n发生错误: {e}")
            print("按回车键继续...")
            input()


if __name__ == "__main__":
    # 设置控制台编码为UTF-8
    if os.name == 'nt':
        os.system('chcp 65001 > nul')

    main()