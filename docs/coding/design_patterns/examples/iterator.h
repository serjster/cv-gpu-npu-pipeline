#pragma once
#include <iostream>
#include <vector>
#include <memory>

// Iterator Pattern: Provides a way to access the elements of an aggregate object
// sequentially without exposing its underlying representation.

namespace iterator_pattern {

// Forward declarations
class MenuItem;

// Iterator interface
template<typename T>
class Iterator {
public:
	virtual ~Iterator() = default;
	virtual bool HasNext() = 0;
	virtual T* Next() = 0;
};

// Menu Item - element we're iterating over
class MenuItem {
private:
	std::string name;
	std::string description;
	bool vegetarian;
	double price;

public:
	MenuItem(const std::string& n, const std::string& desc, bool veg, double p)
		: name(n), description(desc), vegetarian(veg), price(p) {}

	std::string GetName() const { return name; }
	std::string GetDescription() const { return description; }
	double GetPrice() const { return price; }
	bool IsVegetarian() const { return vegetarian; }

	void Print() const {
		std::cout << "  " << name;
		if (vegetarian) std::cout << "(v)";
		std::cout << ", " << price << "\n";
		std::cout << "     -- " << description << "\n";
	}
};

// Aggregate interface
class Menu {
public:
	virtual ~Menu() = default;
	virtual Iterator<MenuItem>* CreateIterator() = 0;
};

// Concrete Iterator for array-based storage
class DinerMenuIterator : public Iterator<MenuItem> {
private:
	MenuItem** items;
	int size;
	int position;

public:
	DinerMenuIterator(MenuItem** menuItems, int count)
		: items(menuItems), size(count), position(0) {}

	bool HasNext() override {
		return position < size && items[position] != nullptr;
	}

	MenuItem* Next() override {
		if (!HasNext()) return nullptr;
		return items[position++];
	}
};

// Concrete Iterator for vector-based storage
class PancakeHouseMenuIterator : public Iterator<MenuItem> {
private:
	std::vector<MenuItem*>& items;
	size_t position;

public:
	explicit PancakeHouseMenuIterator(std::vector<MenuItem*>& menuItems)
		: items(menuItems), position(0) {}

	bool HasNext() override {
		return position < items.size();
	}

	MenuItem* Next() override {
		if (!HasNext()) return nullptr;
		return items[position++];
	}
};

// Concrete Aggregate - uses array
class DinerMenu : public Menu {
private:
	static constexpr int MAX_ITEMS = 6;
	MenuItem* menuItems[MAX_ITEMS];
	int numberOfItems;

public:
	DinerMenu() : numberOfItems(0) {
		for (int i = 0; i < MAX_ITEMS; i++) {
			menuItems[i] = nullptr;
		}

		AddItem("Vegetarian BLT", "(Fakin') Bacon with lettuce & tomato on whole wheat", true, 2.99);
		AddItem("BLT", "Bacon with lettuce & tomato on whole wheat", false, 2.99);
		AddItem("Soup of the day", "Soup of the day, with a side of potato salad", false, 3.29);
		AddItem("Hotdog", "A hot dog, with sauerkraut, relish, onions, topped with cheese", false, 3.05);
		AddItem("Steamed Veggies and Brown Rice", "Steamed vegetables over brown rice", true, 3.99);
		AddItem("Pasta", "Spaghetti with Marinara Sauce, and a slice of sourdough bread", true, 3.89);
	}

	~DinerMenu() {
		for (int i = 0; i < numberOfItems; i++) {
			delete menuItems[i];
		}
	}

	void AddItem(const std::string& name, const std::string& desc, bool veg, double price) {
		if (numberOfItems >= MAX_ITEMS) {
			std::cerr << "Sorry, menu is full! Can't add item to menu\n";
			return;
		}
		menuItems[numberOfItems++] = new MenuItem(name, desc, veg, price);
	}

	Iterator<MenuItem>* CreateIterator() override {
		return new DinerMenuIterator(menuItems, numberOfItems);
	}
};

// Concrete Aggregate - uses vector
class PancakeHouseMenu : public Menu {
private:
	std::vector<MenuItem*> menuItems;

public:
	PancakeHouseMenu() {
		AddItem("K&B's Pancake Breakfast", "Pancakes with scrambled eggs and toast", true, 2.99);
		AddItem("Regular Pancake Breakfast", "Pancakes with fried eggs, sausage", false, 2.99);
		AddItem("Blueberry Pancakes", "Pancakes made with fresh blueberries", true, 3.49);
		AddItem("Waffles", "Waffles with your choice of blueberries or strawberries", true, 3.59);
	}

	~PancakeHouseMenu() {
		for (auto* item : menuItems) {
			delete item;
		}
	}

	void AddItem(const std::string& name, const std::string& desc, bool veg, double price) {
		menuItems.push_back(new MenuItem(name, desc, veg, price));
	}

	Iterator<MenuItem>* CreateIterator() override {
		return new PancakeHouseMenuIterator(menuItems);
	}
};

// Client - Waitress uses Iterator
class Waitress {
private:
	std::vector<Menu*> menus;

public:
	void AddMenu(Menu* menu) {
		menus.push_back(menu);
	}

	void PrintMenu() {
		std::cout << "\nMENU\n----\n";
		for (auto* menu : menus) {
			PrintMenu(menu->CreateIterator());
		}
	}

	void PrintMenu(Iterator<MenuItem>* iterator) {
		while (iterator->HasNext()) {
			MenuItem* menuItem = iterator->Next();
			menuItem->Print();
		}
		delete iterator;
	}

	void PrintVegetarianMenu() {
		std::cout << "\nVEGETARIAN MENU\n---------------\n";
		for (auto* menu : menus) {
			PrintVegetarianMenu(menu->CreateIterator());
		}
	}

	void PrintVegetarianMenu(Iterator<MenuItem>* iterator) {
		while (iterator->HasNext()) {
			MenuItem* menuItem = iterator->Next();
			if (menuItem->IsVegetarian()) {
				menuItem->Print();
			}
		}
		delete iterator;
	}
};

// Modern C++ Iterator using STL-style approach
template<typename T>
class ModernIterator {
public:
	using iterator_category = std::forward_iterator_tag;
	using value_type = T;
	using difference_type = std::ptrdiff_t;
	using pointer = T*;
	using reference = T&;

private:
	pointer ptr;

public:
	explicit ModernIterator(pointer p) : ptr(p) {}

	reference operator*() const { return *ptr; }
	pointer operator->() { return ptr; }

	ModernIterator& operator++() {
		ptr++;
		return *this;
	}

	ModernIterator operator++(int) {
		ModernIterator tmp = *this;
		++(*this);
		return tmp;
	}

	friend bool operator==(const ModernIterator& a, const ModernIterator& b) {
		return a.ptr == b.ptr;
	}

	friend bool operator!=(const ModernIterator& a, const ModernIterator& b) {
		return a.ptr != b.ptr;
	}
};

// Container with STL-style iterators
class ModernContainer {
private:
	std::vector<int> data;

public:
	ModernContainer() {
		data = {1, 2, 3, 4, 5};
	}

	using iterator = ModernIterator<int>;
	using const_iterator = ModernIterator<const int>;

	iterator begin() { return iterator(&data[0]); }
	iterator end() { return iterator(&data[data.size()]); }

	const_iterator begin() const { return const_iterator(&data[0]); }
	const_iterator end() const { return const_iterator(&data[data.size()]); }
};

// Usage example
inline void IteratorPatternDemo() {
	std::cout << "=== Classic Iterator Pattern ===\n";

	PancakeHouseMenu* pancakeHouseMenu = new PancakeHouseMenu();
	DinerMenu* dinerMenu = new DinerMenu();

	Waitress* waitress = new Waitress();
	waitress->AddMenu(pancakeHouseMenu);
	waitress->AddMenu(dinerMenu);

	waitress->PrintMenu();
	waitress->PrintVegetarianMenu();

	// Clean up
	delete waitress;
	delete pancakeHouseMenu;
	delete dinerMenu;

	std::cout << "\n=== Modern C++ Iterator ===\n";
	ModernContainer container;
	for (auto it = container.begin(); it != container.end(); ++it) {
		std::cout << *it << " ";
	}
	std::cout << "\n";

	// Range-based for loop works with our modern iterator
	std::cout << "Using range-based for: ";
	for (int val : container) {
		std::cout << val << " ";
	}
	std::cout << "\n";
}

// Benefits of Iterator Pattern:
// 1. Decouples collection implementation from traversal
// 2. Simplifies the collection interface (Single Responsibility Principle)
// 3. Multiple traversals can be active on same collection
// 4. Uniform interface for traversing different collection types
// 5. Easy to add new traversal algorithms

// Iterator Pattern and Single Responsibility Principle:
// - Collection manages aggregate of objects
// - Iterator handles traversal
// - Each has only one reason to change

// External Iterator vs Internal Iterator:
// - External (shown above): Client controls iteration (HasNext/Next)
// - Internal: Iterator controls iteration, client provides operation to perform

// When to use Iterator:
// 1. Access contents of aggregate without exposing internal structure
// 2. Support multiple traversals of aggregate objects
// 3. Provide uniform interface for traversing different aggregate structures

} // namespace IteratorPattern
