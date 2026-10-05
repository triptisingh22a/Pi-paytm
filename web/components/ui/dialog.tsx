'use client';
// shadcn-style accessible primitive, themed by Munshi's CSS.
import * as Primitive from '@radix-ui/react-dialog';
import type { ReactNode } from 'react';
export function ReceiptDialog({open,onClose,children}:{open:boolean;onClose:()=>void;children:ReactNode}) {
 return <Primitive.Root open={open} onOpenChange={v=>{if(!v)onClose();}}><Primitive.Portal><Primitive.Overlay className="modal-overlay"/><Primitive.Content className="drawer modal-content" aria-describedby={undefined}><Primitive.Title className="sr-only">Calculation receipt</Primitive.Title>{children}</Primitive.Content></Primitive.Portal></Primitive.Root>;
}
