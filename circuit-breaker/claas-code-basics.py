#1. **`__init__` is the setup method:** it runs automatically when you create an object. You only define it when you need starting values.
#2. **`self` means “this object”:** use `self.name`, `self.age`, etc. to store values inside each object.
#3. **Python uses one `__init__`:** unlike Java, Python does not support multiple constructors. Use default values, keyword arguments like `Dog(age=5)`, or `*` to force keyword-only arguments.



class Dog:
    def __init__(self, name='', sound=''):
        self.name = name
        self.sound = sound

#dog = Dog("Bruno")

cat = Dog('', 'Meow')

#print(dog.name)
print(cat.sound)