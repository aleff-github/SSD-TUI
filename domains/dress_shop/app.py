import csv
import sys
from getpass import getpass
from pathlib import Path
from typing import Any, Callable, Tuple
from wsgiref import headers

import requests
from domains.dress_loan.menu import Entry, Menu, MenuDescription
from valid8 import ValidationError, validate
import jwt
import re
import uuid

from domains.dress.domain import *
from domains.dress_shop.domain import *
from domains.user.domain import *
from domains.dress_shop.secret import *

from jwt.algorithms import get_default_algorithms

api_server = 'https://ssd.pingflood.tk/api/v1'


class App:
    __filename = Path(__file__).parent.parent / 'shoppingList.csv'
    __delimiter = '\t'
    __logged = False
    __key = None
    __id_dictionary = []

    def __init__(self):
        self.__first_menu = self.init_first_menu()
        self.id_user = None
        self.__choice_menu = self.__init_choice_menu()
        self.__dressloan_menu = self.__init_dressloans_menu()
        self.__dress_menu = self.__init_dress_menu()
        self.__dressList = DressList()
        self.__dressloanList = DressLoanList()
        get_default_algorithms()

    def init_first_menu(self) -> Menu:
        return Menu.Builder(MenuDescription('Dressy'),
                            auto_select=lambda: print('Welcome! Please select an option')) \
            .with_entry(Entry.create('1', 'Login', is_logged=lambda: self.__login())) \
            .with_entry(Entry.create('0', 'Exit', on_selected=lambda: print('Bye Bye!\n'), is_exit=True)) \
            .build()

    def __init_choice_menu(self) -> Menu:
        return Menu.Builder(MenuDescription('Dressy - Choice Menu'),
                            auto_select=lambda: print('Select the menu to display')) \
            .with_entry(Entry.create('1', 'Dressloan', on_selected=lambda: self.__run_dressloan_menu())) \
            .with_entry(Entry.create('2', 'Dress', on_selected=lambda: self.__run_dress_menu())) \
            .with_entry(Entry.create('0', 'Go back to Login', on_selected=lambda: print('Logged out\n'), is_exit=True)) \
            .build()

    
    def __init_dressloans_menu(self) -> Menu:
         return Menu.Builder(MenuDescription('Dressy - Dress Loan Menu'),
                            auto_select=lambda: self.__print_dressloans()) \
            .with_entry(Entry.create('1', 'Sort by total price', on_selected=lambda: self.__dressloanList.sort_by_total_price()))\
            .with_entry(Entry.create('0', 'Go back to Choice Menu', on_selected=lambda: print('Make a choice\n'), is_exit=True)) \
            .build()

    def __init_dress_menu(self) -> Menu:
         return Menu.Builder(MenuDescription('Dressy - Dress Menu'),
                            auto_select=lambda: self.__print_dresses()) \
            .with_entry(Entry.create('1', 'Sort by price', on_selected=lambda: self.__dressList.sort_by_price()))\
            .with_entry(Entry.create('2', 'Add dress', on_selected=lambda: self.__add_dress()))\
            .with_entry(Entry.create('3', 'Delete dress', on_selected=lambda: self.__remove_dress()))\
            .with_entry(Entry.create('0', 'Go back to Choice Menu', on_selected=lambda: print('Make a choice\n'), is_exit=True)) \
            .build()

    def run(self) -> None:
        try:
            self.__run()
        except Exception as e:
            print(e)
            print('Panic error!', file=sys.stderr)

    def __run(self) -> None:
        while not self.__first_menu.run() == (True, False):
            try:
                self.__fetch_dressloan()
                self.__fetch_dress()
            except ValueError as e:
                print(e)
            except RuntimeError:
                print('Failed to connect to the server! Try later!')
                return
            self.__choice_menu.run()

    def __run_dressloan_menu(self) -> None:
        self.__dressloan_menu.run()

    def __run_dress_menu(self) -> None:
        self.__dress_menu.run()

    def __login(self) -> bool:
        done = False
        while not done:
            username = self.__read("Username ", Username)
            if username.value == '0':
                return False
            password = self.__read("Password ", Password)
            if password.value == '0':
                return False

            res = requests.post(url=f'{api_server}/login/', data={'username': username, 'password': password},
                                verify=True)

            if res.status_code != 200:
                print('This user does not exist!')
            else:
                self.__key = res.json()['access']
                print(self.decode_token_role(self.__key))
                print('Login success')
                done = True
        return True

    def decode_token_role(self, key):
        secret=secret_key()
        decoded = jwt.decode(key, secret, algorithms=['HS512'])
        return decoded['groups'][0]


    @staticmethod
    def __read(prompt: str, builder: Callable) -> Any:
        while True:
            try:
                if prompt != 'Password':
                    line = input(f'{prompt}: ')
                else:
                    line = input(f'{prompt}: ')

                res = builder(line.strip())
                return res
            except (TypeError, ValueError, ValidationError) as e:
                print('Format not satisfied')

    def __fetch_dress(self) -> None:
        res = requests.get(url=f'{api_server}/dress/',
                           headers={'Authorization': f'Bearer {self.__key}'}, verify=True)

        if res.status_code != 200:
            raise RuntimeError()

        json = res.json()
        if json is None:
            return
        for item in json:
            uuid = DressID(str(item['id']))
            brand = Brand(str(item['brandType']))
            price = Price.create(int(int(item['priceInCents']) / 100), int(item['priceInCents']) % 100)
            material = Material(str(item['materialType']))
            color = Color(str(item['colorType']))
            size = Size(int(item['size']))
            description = Description(str(item['description']))
            deleted = Deleted(bool(item['deleted']))
            dress = Dress(uuid, brand, price, material, color, size, description, deleted)
            self.__dressList.add_dress(dress)

    def __fetch_dressloan(self) -> None:
        res = requests.get(url=f'{api_server}/loan/',
                        headers={'Authorization': f'Bearer {self.__key}'}, verify=True)
        
        if res.status_code != 200:
            raise RuntimeError()

        json = res.json()
        if json is None:
            return

        for item in json:
            uuidDressLoan = DressLoanID(str(item['id']))
            startDate = StartDate(str(item['startDate']))
            endDate = EndDate(str(item['endDate']))
            dressID = DressID(str(item['dress']))
            loaner = UserID(int(item['loaner']))
            totalPrice = Price(int(item['totalPrice']))
            loanDurationDays = DurationDays (int(item['loanDurationDays']))
            insertBy = UserID(int(item['insertBy']))
            terminated = Terminated(bool(item['terminated']))
            dressloan = DressLoan(uuidDressLoan, startDate, endDate, dressID, loaner, totalPrice, loanDurationDays, insertBy, terminated)
            self.__dressloanList.add_dressloan(dressloan)

    def __print_dressloans(self) -> None:
        if self.__dressloanList.length() == 0:
            return
        print_sep = lambda: print('-' * 180)
        print_sep()
        fmt = '%-10s %-30s  %-20s  %-20s %-30s %-10s'
        print(fmt % ('Number', 'Description', 'Start-Date', 'End-Date', 'Total Price', 'Terminated'))
        print_sep()
        for index in range(self.__dressloanList.length()):
            item = self.__dressloanList.item(index)
            print(fmt % (index + 1, item.startDate.value, item.startDate.value,
                         item.endDate.value, item.totalPrice.__str__(), item.terminated.value))
        print_sep()

    def __print_dresses(self) -> None:
        if self.__dressList.length() == 0:
            return
        print_sep = lambda: print('-' * 180)
        print_sep()
        fmt = '%-10s %-20s  %-20s  %-20s %-20s %-20s %-30s %-10s'
        print(fmt % ('Number', 'Brand', 'Price', 'Material', 'Color', 'Size', 'Description', 'Deleted'))
        print_sep()
        for index in range(self.__dressList.length()):
            item = self.__dressList.item(index)
            print(fmt % (index + 1, item.brand.value, item.price.__str__(), item.material.value,
                         item.color.value, item.size.value, item.description.value, item.deleted.value))
        print_sep()

    def __read_dress(self) -> Tuple[DressID, Brand, Price, Material, Color, Size, Description, Deleted]:
        #generare un uuid randomico in stringa
        id = DressID("517e90e5-2020-40d7-aa3a-3507c1ca24dd")
        dress_id = id
        brand = self.__read('Brand', Brand)
        price = self.__read('Price', Price.parse)
        material = self.__read('Material', Material)
        color = self.__read('Color', Color)
        size = self.__read('Size', int)
        real_size = Size(size)
        description = self.__read('Description', Description)
        deleted = Deleted(False)
        return dress_id, brand, price, material, color, real_size, description, deleted

    def __add_dress(self) -> None:
        newDress = Dress(*self.__read_dress())
        self.__dressList.add_dress(newDress)
        print('Dress added!\n')
        #chiamata al backend permanente?

    def __remove_dress(self) -> None :
        def builder(value: str) -> int:
            validate('value', int(value), min_value=0, max_value=self.__dressList.length())
            return int(value)

        index = self.__read('Index (0 to cancel)', builder)
        if index == 0:
            print('Cancelled!')
            return
        self.__dressList.remove_dress_by_index(index - 1)
        print('Dress removed!')
        #chiamata al backend permanente?