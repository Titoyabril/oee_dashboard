"""
Browse OPC UA server to discover node structure
"""
import asyncio
from asyncua import Client


async def browse_nodes(node, indent=0):
    """Recursively browse OPC UA nodes"""
    try:
        browse_name = await node.read_browse_name()
        node_class = await node.read_node_class()
        node_id = node.nodeid.to_string()

        print(f"{'  ' * indent}{browse_name.Name} [{node_class.name}] - {node_id}")

        # If it's a variable, print its value
        if node_class.name == 'Variable':
            try:
                value = await node.read_value()
                print(f"{'  ' * indent}  Value: {value}")
            except:
                pass

        # Browse children
        if indent < 5:  # Limit depth
            children = await node.get_children()
            for child in children:
                await browse_nodes(child, indent + 1)

    except Exception as e:
        print(f"{'  ' * indent}Error: {e}")


async def main():
    endpoint = "opc.tcp://localhost:4841/freeopcua/server/"
    print(f"Browsing OPC UA server: {endpoint}")
    print("=" * 80)

    client = Client(url=endpoint)
    await client.connect()

    # Start browsing from Objects folder
    print("\nBrowsing from Objects folder:")
    objects = client.nodes.objects
    await browse_nodes(objects)

    await client.disconnect()


if __name__ == '__main__':
    asyncio.run(main())
